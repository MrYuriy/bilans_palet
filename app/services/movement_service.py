from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exc import (
    BadRequestException,
    ForbiddenException,
    ObjectNotFoundException,
)
from app.core.timeutils import local_now
from app.models.area import Area
from app.models.movement import Movement, MovementLine, MovementType
from app.models.user import User
from app.repositories.area_repo import AreaRepository
from app.repositories.movement_repo import MovementRepository
from app.repositories.pallet_type_repo import PalletTypeRepository
from app.repositories.quality_repo import QualityRepository
from app.schemas.movement import (
    MOVEMENT_LABELS,
    MovementCreate,
    MovementLineIn,
    MovementOut,
    MovementTypeOut,
    UserRef,
)
from app.services.permission_service import PermissionService

# Movements entered as positive quantities, and the sign they get in the balance.
SIGNS = {
    MovementType.RECEIPT: 1,
    MovementType.LM_PURCHASE: 1,
    MovementType.SHIPMENT: -1,
}


def movement_out(movement: Movement) -> MovementOut:
    return MovementOut(
        uuid=movement.uuid,
        type=movement.type,
        type_label=MOVEMENT_LABELS[movement.type],
        area=movement.area,
        user=UserRef.model_validate(movement.user),
        operation_date=movement.operation_date,
        document_number=movement.document_number,
        comment=movement.comment,
        created_at=movement.created_at,
        lines=movement.lines,
    )


def _clean(text: str | None) -> str | None:
    return (text or "").strip() or None


class MovementService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MovementRepository(session)
        self.area_repo = AreaRepository(session)
        self.pallet_type_repo = PalletTypeRepository(session)
        self.quality_repo = QualityRepository(session)
        self.permissions = PermissionService()

    @staticmethod
    def types() -> list[MovementTypeOut]:
        return [MovementTypeOut(code=t, label=MOVEMENT_LABELS[t]) for t in MovementType]

    # ---------- reading ----------

    def _readable_areas(self, user: User) -> list[UUID] | None:
        """None = every area; otherwise the user's assigned areas."""
        if self.permissions.reads_every_area(user.role.name):
            return None
        return [a.uuid for a in user.areas]

    async def search(
        self,
        user: User,
        area_uuid: UUID | None = None,
        movement_type: MovementType | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MovementOut], int]:
        readable = self._readable_areas(user)
        if area_uuid is not None:
            if readable is not None and area_uuid not in readable:
                raise ForbiddenException("Brak dostępu do obszaru")
            readable = [area_uuid]

        rows, total = await self.repo.search(
            readable, movement_type, date_from, date_to, limit, offset
        )
        return [movement_out(m) for m in rows], total

    async def get(self, user: User, movement_uuid: UUID) -> MovementOut:
        movement = await self.repo.get_with_details(movement_uuid)
        if movement is None:
            raise ObjectNotFoundException("Nie znaleziono ruchu")
        readable = self._readable_areas(user)
        if readable is not None and movement.area_uuid not in readable:
            raise ForbiddenException("Brak dostępu do obszaru")
        return movement_out(movement)

    # ---------- creating ----------

    async def _area(self, user: User, area_uuid: UUID | None) -> Area:
        assigned = [a for a in user.areas if a.is_active]

        if area_uuid is None:
            if len(assigned) == 1:
                return assigned[0]
            raise BadRequestException("Wybierz obszar")

        area = await self.area_repo.get_one(uuid=area_uuid)
        if area is None:
            raise BadRequestException("Nieznany obszar")
        if not area.is_active:
            raise BadRequestException(f"Obszar „{area.name}” jest nieaktywny")
        if not self.permissions.enters_in_any_area(
            user.role.name
        ) and area.uuid not in {a.uuid for a in assigned}:
            raise ForbiddenException("Brak dostępu do obszaru")
        return area

    @staticmethod
    def _operation_date(value: date | None) -> date:
        today = local_now().date()
        if value is None:
            return today
        if value > today:
            raise BadRequestException("Data operacji nie może być z przyszłości")
        return value

    async def _lines(
        self, movement_type: MovementType, lines: list[MovementLineIn]
    ) -> list[MovementLine]:
        if not lines:
            raise BadRequestException("Dodaj co najmniej jedną pozycję")

        pallet_types = {
            t.uuid: t
            for t in await self.pallet_type_repo.list_all_by_ids(
                list({line.pallet_type_uuid for line in lines})
            )
        }
        qualities = {
            q.uuid: q
            for q in await self.quality_repo.list_all_by_ids(
                list({line.quality_uuid for line in lines})
            )
        }

        result = []
        for position, line in enumerate(lines, start=1):
            pallet_type = pallet_types.get(line.pallet_type_uuid)
            if pallet_type is None:
                raise BadRequestException("Nieznany typ palety")
            if not pallet_type.is_active:
                raise BadRequestException(
                    f"Typ palety „{pallet_type.name}” jest nieaktywny"
                )

            quality = qualities.get(line.quality_uuid)
            if quality is None:
                raise BadRequestException("Nieznana jakość")
            if not quality.is_active:
                raise BadRequestException(f"Jakość „{quality.name}” jest nieaktywna")

            if movement_type == MovementType.CORRECTION:
                if line.quantity == 0:
                    raise BadRequestException("Ilość korekty nie może być zerowa")
                quantity = line.quantity
            else:
                if line.quantity <= 0:
                    raise BadRequestException("Ilość musi być większa od zera")
                quantity = SIGNS[movement_type] * line.quantity

            result.append(
                MovementLine(
                    position=position,
                    pallet_type_uuid=pallet_type.uuid,
                    quality_uuid=quality.uuid,
                    quantity=quantity,
                )
            )
        return result

    async def create(self, user: User, data: MovementCreate) -> MovementOut:
        area = await self._area(user, data.area_uuid)
        operation_date = self._operation_date(data.operation_date)
        comment = _clean(data.comment)

        if data.type == MovementType.CORRECTION and comment is None:
            raise BadRequestException("Podaj powód korekty w komentarzu")

        lines = await self._lines(data.type, data.lines)

        movement = Movement(
            type=data.type,
            area_uuid=area.uuid,
            user_uuid=user.uuid,
            operation_date=operation_date,
            document_number=_clean(data.document_number),
            comment=comment,
            lines=lines,
        )
        self.session.add(movement)
        await self.session.flush()

        # Read it back whole (area, user, line names). Detaching the new object
        # first makes the read build it fresh; a refresh with populate_existing
        # would also reset the current user, who is the movement's author.
        self.session.expunge(movement)
        return movement_out(await self.repo.get_with_details(movement.uuid))
