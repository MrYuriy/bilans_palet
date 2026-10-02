from sqlalchemy.orm import joinedload, selectinload

from app.models.user import User
from app.repositories.base import BaseRepository

# Role and assigned areas are needed wherever a user is shown or authorised.
_WITH_ROLE_AND_AREAS = [joinedload(User.role), selectinload(User.areas)]


class UserRepository(BaseRepository[User]):
    def __init__(self, session):
        super().__init__(session, User)

    async def get_by_username(self, username: str) -> User | None:
        return await self.get_one(username=username, options=_WITH_ROLE_AND_AREAS)

    async def get_with_role(self, user_uuid) -> User | None:
        return await self.get_one(uuid=user_uuid, options=_WITH_ROLE_AND_AREAS)

    async def get_all_with_roles(self) -> list[User]:
        return await self.get_all(
            order_by=[User.username], options=_WITH_ROLE_AND_AREAS
        )
