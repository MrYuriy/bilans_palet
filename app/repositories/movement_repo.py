from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.models.movement import Movement, MovementLine, MovementType
from app.repositories.base import BaseRepository

_DETAILS = [
    joinedload(Movement.area),
    joinedload(Movement.user),
    selectinload(Movement.lines).joinedload(MovementLine.pallet_type),
    selectinload(Movement.lines).joinedload(MovementLine.quality),
]


class MovementRepository(BaseRepository[Movement]):
    def __init__(self, session):
        super().__init__(session, Movement)

    async def get_with_details(self, movement_uuid: UUID) -> Movement | None:
        return await self.get_one(uuid=movement_uuid, options=_DETAILS)

    async def search(
        self,
        area_uuids: list[UUID] | None = None,
        movement_type: MovementType | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Movement], int]:
        """Newest first. ``area_uuids=None`` means every area."""
        conditions = []
        if area_uuids is not None:
            conditions.append(Movement.area_uuid.in_(area_uuids))
        if movement_type is not None:
            conditions.append(Movement.type == movement_type)
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
