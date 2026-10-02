from uuid import UUID

from sqlalchemy import select

from app.models.area import Area
from app.repositories.base import BaseRepository


class AreaRepository(BaseRepository[Area]):
    def __init__(self, session):
        super().__init__(session, Area)

    async def lock(self, area_uuid: UUID) -> None:
        """Hold the area row until the transaction ends (Postgres SELECT ... FOR
        UPDATE), so two movements of one area are checked one after the other."""
        await self.session.execute(
            select(Area.uuid).where(Area.uuid == area_uuid).with_for_update()
        )
