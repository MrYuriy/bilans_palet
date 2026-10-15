from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exc import (
    BadRequestException,
    ForbiddenException,
    ObjectNotFoundException,
)
from app.models.carrier_type import CarrierType
from app.models.movement import Movement, MovementLine, MovementType
from app.models.user import User
from app.repositories.carrier_type_repo import CarrierTypeRepository
from app.repositories.movement_repo import MovementRepository
from app.repositories.stock_lock import StockLock
from app.schemas.movement import (
    InventoryLineOut,
    MovementCreate,
    MovementLineIn,
    MovementOut,
    MovementTypeOut,
    UserRef,
)
from app.services.day_close_service import ensure_day_open
from app.services.operation_catalog import OPERATIONS, Operation
from app.services.permission_service import PermissionService
from app.services.settings_service import SettingsService


def movement_out(movement: Movement) -> MovementOut:
    return MovementOut(
        uuid=movement.uuid,
        type=movement.type,
        type_label=OPERATIONS[movement.type].label,
        user=UserRef.model_validate(movement.user),
        operation_date=movement.operation_date,
        document_number=movement.document_number,
        comment=movement.comment,
        created_at=movement.created_at,
        lines=movement.lines,
        inventory_lines=(
            [
                InventoryLineOut(
                    carrier_type=row.carrier_type,
                    system_quantity=row.system_quantity,
                    counted_quantity=row.counted_quantity,
                    difference=row.counted_quantity - row.system_quantity,
                )
                for row in movement.inventory_lines
            ]
            if movement.type == MovementType.INVENTORY
            else None
        ),
    )


def clean_text(text: str | None) -> str | None:
    return (text or "").strip() or None


class MovementService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MovementRepository(session)
        self.type_repo = CarrierTypeRepository(session)
        self.lock = StockLock(session)
        self.permissions = PermissionService()

    def types(self, user: User) -> list[MovementTypeOut]:
        return [
            MovementTypeOut(
                code=op.type,
                label=op.label,
                sign=op.sign,
                note_required=op.note_required,
                counted_types_only=op.counted_types_only,
                can_enter=op.type != MovementType.INVENTORY
                and not op.imported
                and self.permissions.has_access(user.role.name, op.module),
            )
            for op in OPERATIONS.values()
        ]

    def check_allowed(self, user: User, operation: Operation) -> None:
        if not self.permissions.has_access(user.role.name, operation.module):
            raise ForbiddenException("Brak uprawnień")

    # ---------- reading ----------

    async def search(
        self,
        movement_type: MovementType | None = None,
        carrier_type_uuid: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MovementOut], int]:
        rows, total = await self.repo.search(
            movement_type, carrier_type_uuid, date_from, date_to, limit, offset
        )
        return [movement_out(m) for m in rows], total

    async def get(self, movement_uuid: UUID) -> MovementOut:
        movement = await self.repo.get_with_details(movement_uuid)
        if movement is None:
            raise ObjectNotFoundException("Nie znaleziono ruchu")
        return movement_out(movement)

    # ---------- creating ----------

    async def operation_date(self, value: date | None) -> date:
        """The warehouse day of the movement; today's when left out."""
        today = await SettingsService(self.session).current_day()
        if value is None:
            return today
        if value > today:
            raise BadRequestException("Data operacji nie może być z przyszłości")
        return value

    async def carrier_types(self, uuids: set[UUID]) -> dict[UUID, CarrierType]:
        """The active carrier types asked for; an unknown or inactive one is refused."""
        found = {t.uuid: t for t in await self.type_repo.list_all_by_ids(list(uuids))}
        for type_uuid in uuids:
            carrier_type = found.get(type_uuid)
            if carrier_type is None:
                raise BadRequestException("Nieznany typ nośnika")
            if not carrier_type.is_active:
                raise BadRequestException(
                    f"Typ nośnika „{carrier_type.name}” jest nieaktywny"
                )
        return found

    async def _lines(
        self, operation: Operation, lines: list[MovementLineIn]
    ) -> list[MovementLine]:
        if not lines:
            raise BadRequestException("Dodaj co najmniej jedną pozycję")

        reclassification = operation.type == MovementType.RECLASSIFICATION
        types = await self.carrier_types(
            {line.carrier_type_uuid for line in lines}
            | {line.to_carrier_type_uuid for line in lines if line.to_carrier_type_uuid}
        )

        result: list[MovementLine] = []

        def add(type_uuid: UUID, quantity: int) -> None:
            result.append(
                MovementLine(
                    position=len(result) + 1,
                    carrier_type_uuid=type_uuid,
                    quantity=quantity,
                )
            )

        for line in lines:
            carrier_type = types[line.carrier_type_uuid]

            if line.to_carrier_type_uuid is not None and not reclassification:
                raise BadRequestException("Typ docelowy dotyczy tylko przeksięgowania")

            if operation.counted_types_only and not carrier_type.count_in_reports:
                raise BadRequestException(
                    f"„{operation.label}” dotyczy tylko typów liczonych w raportach,"
                    f" nie „{carrier_type.name}”"
                )

            if operation.type == MovementType.CORRECTION:
                if line.quantity == 0:
                    raise BadRequestException("Ilość korekty nie może być zerowa")
                add(carrier_type.uuid, line.quantity)
                continue

            if line.quantity <= 0:
                raise BadRequestException("Ilość musi być większa od zera")

            if not reclassification:
                add(carrier_type.uuid, operation.sign * line.quantity)
                continue

            # Re-classification: off one carrier type, onto another, any direction.
            if line.to_carrier_type_uuid is None:
                raise BadRequestException("Podaj typ docelowy przeksięgowania")
            if line.to_carrier_type_uuid == carrier_type.uuid:
                raise BadRequestException(
                    "Przeksięgowanie wymaga dwóch różnych typów nośników"
                )
            add(carrier_type.uuid, -line.quantity)
            add(line.to_carrier_type_uuid, line.quantity)

        return result

    async def create(self, user: User, data: MovementCreate) -> MovementOut:
        operation = OPERATIONS[data.type]
        if operation.type == MovementType.INVENTORY:
            raise BadRequestException("Inwentaryzację wprowadza się arkuszem spisu")
        if operation.imported:
            raise BadRequestException(f"„{operation.label}” księguje się z pliku")
        self.check_allowed(user, operation)

        operation_date = await self.operation_date(data.operation_date)
        comment = clean_text(data.comment)
        if operation.note_required and comment is None:
            raise BadRequestException(f"„{operation.label}” wymaga notatki")

        lines = await self._lines(operation, data.lines)

        # Held until commit: a day being closed waits for this movement, or this
        # movement sees that its day was closed.
        await self.lock.shared()
        await ensure_day_open(self.session, operation_date)

        movement = Movement(
            type=operation.type,
            user_uuid=user.uuid,
            operation_date=operation_date,
            document_number=clean_text(data.document_number),
            comment=comment,
            lines=lines,
        )
        self.session.add(movement)
        await self.session.flush()

        # Read it back whole (user, line names). Detaching the new object first
        # makes the read build it fresh; a refresh with populate_existing would
        # also reset the current user, who is the movement's author.
        self.session.expunge(movement)
        return movement_out(await self.repo.get_with_details(movement.uuid))
