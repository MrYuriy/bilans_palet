from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.data_import import DataImport, ImportDay
from app.models.movement import MovementType
from app.repositories.base import BaseRepository


class ImportRepository(BaseRepository[DataImport]):
    def __init__(self, session):
        super().__init__(session, DataImport)

    async def recent(self, source: str | None, limit: int) -> list[DataImport]:
        query = (
            select(DataImport)
            .options(joinedload(DataImport.user))
            .order_by(DataImport.created_at.desc())
            .limit(limit)
        )
        if source is not None:
            query = query.where(DataImport.source == source)
        return list((await self.session.execute(query)).scalars().all())

    async def booked_days(
        self,
        source: str,
        carrier_type_uuid: UUID,
        movement_type: MovementType,
        first: date,
        last: date,
    ) -> dict[date, ImportDay]:
        """What was booked so far per day of the range."""
        query = select(ImportDay).where(
            ImportDay.source == source,
            ImportDay.carrier_type_uuid == carrier_type_uuid,
            ImportDay.movement_type == movement_type,
            ImportDay.day >= first,
            ImportDay.day <= last,
        )
        return {row.day: row for row in (await self.session.execute(query)).scalars()}
