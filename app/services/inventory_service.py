from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exc import BadRequestException
from app.models.inventory import InventoryLine
from app.models.movement import Movement, MovementLine, MovementType
from app.models.pallet_type import PalletType
from app.models.quality import Quality
from app.models.user import User
from app.schemas.common import NamedRef
from app.schemas.movement import InventoryCreate, MovementOut, SheetRowOut
from app.services.movement_service import MovementService, clean_text, movement_out
from app.services.settings_service import SettingsService


class InventoryService:
    """Stock counts (inwentaryzacja) of one area.

    A count is dated today and approved in one step. The system balance is read
    when it is approved, so the difference is right however long counting took.
    Only the counted rows change; the area's balance of each becomes exactly what
    was counted. The whole sheet is kept, also the rows that matched.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.movements = MovementService(session)

    async def sheet(self, user: User, area_uuid: UUID | None) -> list[SheetRowOut]:
        """An empty count sheet: every active pallet type and quality, with what
        the system holds now."""
        area = await self.movements.resolve_area(user, area_uuid)
        balances = await self.movements.repo.balances(area.uuid)
        pallet_types = await self.movements.pallet_type_repo.get_all(
            order_by=[PalletType.name], is_active=True
        )
        qualities = await self.movements.quality_repo.get_all(
            order_by=[Quality.sort_order], is_active=True
        )
        return [
            SheetRowOut(
                pallet_type=NamedRef.model_validate(t),
                quality=NamedRef.model_validate(q),
                system_quantity=balances.get((t.uuid, q.uuid), 0),
            )
            for t in pallet_types
            for q in qualities
        ]

    async def create(self, user: User, data: InventoryCreate) -> MovementOut:
        area = await self.movements.resolve_area(user, data.area_uuid)
        if not data.lines:
            raise BadRequestException("Dodaj co najmniej jedną pozycję")

        pallet_types = {
            t.uuid: t
            for t in await self.movements.pallet_type_repo.list_all_by_ids(
                list({line.pallet_type_uuid for line in data.lines})
            )
        }
        qualities = {
            q.uuid: q
            for q in await self.movements.quality_repo.list_all_by_ids(
                list({line.quality_uuid for line in data.lines})
            )
        }

        seen: set[tuple[UUID, UUID]] = set()
        for line in data.lines:
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
            if line.counted_quantity < 0:
                raise BadRequestException("Policzona ilość nie może być ujemna")

            key = (pallet_type.uuid, quality.uuid)
            if key in seen:
                raise BadRequestException(
                    f"Pozycja {pallet_type.name} / {quality.name} występuje dwa razy"
                )
            seen.add(key)

        # The system balance is read under the area lock, so no movement of this
        # area can slip in between reading it and recording the difference.
        await self.movements.area_repo.lock(area.uuid)
        balances = await self.movements.repo.balances(area.uuid)

        sheet: list[InventoryLine] = []
        differences: list[MovementLine] = []
        for position, line in enumerate(data.lines, start=1):
            system = balances.get((line.pallet_type_uuid, line.quality_uuid), 0)
            sheet.append(
                InventoryLine(
                    position=position,
                    pallet_type_uuid=line.pallet_type_uuid,
                    quality_uuid=line.quality_uuid,
                    system_quantity=system,
                    counted_quantity=line.counted_quantity,
                )
            )
            if line.counted_quantity != system:
                differences.append(
                    MovementLine(
                        position=len(differences) + 1,
                        pallet_type_uuid=line.pallet_type_uuid,
                        quality_uuid=line.quality_uuid,
                        quantity=line.counted_quantity - system,
                    )
                )

        movement = Movement(
            type=MovementType.INVENTORY,
            area_uuid=area.uuid,
            user_uuid=user.uuid,
            operation_date=await SettingsService(self.session).current_day(),
            document_number=clean_text(data.document_number),
            comment=clean_text(data.comment),
            lines=differences,
            inventory_lines=sheet,
        )
        self.session.add(movement)
        await self.session.flush()

        # Read it back whole; see MovementService.create for why expunge.
        self.session.expunge(movement)
        return movement_out(await self.movements.repo.get_with_details(movement.uuid))
