from datetime import date
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.orm import joinedload, selectinload

from app.models.inventory import InventoryLine
from app.models.movement import Movement, MovementLine, MovementType
from app.repositories.base import BaseRepository

_DETAILS = [
    joinedload(Movement.user),
    selectinload(Movement.lines).joinedload(MovementLine.carrier_type),
    selectinload(Movement.inventory_lines).joinedload(InventoryLine.carrier_type),
]


class MovementRepository(BaseRepository[Movement]):
    def __init__(self, session):
        super().__init__(session, Movement)

    async def get_with_details(self, movement_uuid: UUID) -> Movement | None:
        return await self.get_one(uuid=movement_uuid, options=_DETAILS)

    async def search(
        self,
        movement_type: MovementType | None = None,
        carrier_type_uuid: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Movement], int]:
        """Newest first. A carrier type keeps the movements with a line of it."""
        conditions = []
        if movement_type is not None:
            conditions.append(Movement.type == movement_type)
        if carrier_type_uuid is not None:
            conditions.append(
                exists().where(
                    MovementLine.movement_uuid == Movement.uuid,
                    MovementLine.carrier_type_uuid == carrier_type_uuid,
                )
            )
        if date_from is not None:
            conditions.append(Movement.operation_date >= date_from)
        if date_to is not None:
            conditions.append(Movement.operation_date <= date_to)

        query = (
            select(Movement)
            .where(*conditions)
            .options(*_DETAILS)
            .order_by(Movement.operation_date.desc(), Movement.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        total = select(func.count()).select_from(Movement).where(*conditions)

        rows = (await self.session.execute(query)).scalars().unique().all()
        return list(rows), (await self.session.execute(total)).scalar_one()

    async def balances(self) -> dict[UUID, int]:
        """Current stock per carrier type that has any line."""
        query = select(
            MovementLine.carrier_type_uuid, func.sum(MovementLine.quantity)
        ).group_by(MovementLine.carrier_type_uuid)
        return dict((await self.session.execute(query)).all())
