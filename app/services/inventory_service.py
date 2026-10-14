from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exc import BadRequestException
from app.models.inventory import InventoryLine
from app.models.movement import Movement, MovementLine, MovementType
from app.models.user import User
from app.schemas.common import NamedRef
from app.schemas.movement import InventoryCreate, MovementOut, SheetRowOut
from app.services.day_close_service import ensure_day_open
from app.services.movement_service import MovementService, clean_text, movement_out
from app.services.operation_catalog import OPERATIONS
from app.services.settings_service import SettingsService


class InventoryService:
    """Stock counts (inwentaryzacja), also the starting stock (stan początkowy).

    A count is dated today and approved in one step. The system balance is read
    when it is approved, so the difference is right however long counting took.
    Only the counted rows change; the stock of each becomes exactly what was
    counted. The whole sheet is kept, also the rows that matched.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.movements = MovementService(session)

    def check_allowed(self, user: User) -> None:
        self.movements.check_allowed(user, OPERATIONS[MovementType.INVENTORY])

    async def sheet(self, user: User) -> list[SheetRowOut]:
        """An empty count sheet: every active carrier type, with what the system
        holds now."""
        self.check_allowed(user)
        balances = await self.movements.repo.balances()
        return [
            SheetRowOut(
                group=NamedRef.model_validate(t.group),
                carrier_type=NamedRef.model_validate(t),
                system_quantity=balances.get(t.uuid, 0),
            )
            for t in await self.movements.type_repo.list_with_group(active=True)
        ]

    async def create(self, user: User, data: InventoryCreate) -> MovementOut:
        self.check_allowed(user)
        if not data.lines:
            raise BadRequestException("Dodaj co najmniej jedną pozycję")

        types = await self.movements.carrier_types(
            {line.carrier_type_uuid for line in data.lines}
        )
        seen = set()
        for line in data.lines:
            if line.counted_quantity < 0:
                raise BadRequestException("Policzona ilość nie może być ujemna")
            if line.carrier_type_uuid in seen:
                name = types[line.carrier_type_uuid].name
                raise BadRequestException(f"Pozycja {name} występuje dwa razy")
            seen.add(line.carrier_type_uuid)

        # Exclusive: no movement slips in between reading the system balance
        # and recording the difference.
        await self.movements.lock.exclusive()
        today = await SettingsService(self.session).current_day()
        await ensure_day_open(self.session, today)
        balances = await self.movements.repo.balances()

        sheet: list[InventoryLine] = []
        differences: list[MovementLine] = []
        for position, line in enumerate(data.lines, start=1):
            system = balances.get(line.carrier_type_uuid, 0)
            sheet.append(
                InventoryLine(
                    position=position,
                    carrier_type_uuid=line.carrier_type_uuid,
                    system_quantity=system,
                    counted_quantity=line.counted_quantity,
                )
            )
            if line.counted_quantity != system:
                differences.append(
                    MovementLine(
                        position=len(differences) + 1,
                        carrier_type_uuid=line.carrier_type_uuid,
                        quantity=line.counted_quantity - system,
                    )
                )

        movement = Movement(
            type=MovementType.INVENTORY,
            user_uuid=user.uuid,
            operation_date=today,
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
