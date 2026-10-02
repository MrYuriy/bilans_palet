from app.models.role import Role
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    def __init__(self, session):
        super().__init__(session, Role)

    async def get_by_name(self, name: str) -> Role | None:
        return await self.get_one(name=name)
