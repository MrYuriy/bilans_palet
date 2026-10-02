from uuid import UUID

from app.core.exc import BadRequestException, ObjectNotFoundException
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.user import RoleOut, UserOut


def _user_out(user: User, role_name: str) -> UserOut:
    return UserOut(
        uuid=user.uuid,
        username=user.username,
        role=role_name,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
    )


class UserService:
    def __init__(self, session):
        self.repo = UserRepository(session)
        self.role_repo = RoleRepository(session)

    async def _role(self, role_name: str) -> Role:
        role = await self.role_repo.get_by_name(role_name)
        if role is None:
            raise BadRequestException(f"Rola '{role_name}' nie istnieje")
        return role

    async def list_users(self) -> list[UserOut]:
        users = await self.repo.get_all_with_roles()
        return [_user_out(u, u.role.name) for u in users]

    async def list_roles(self) -> list[RoleOut]:
        roles = await self.role_repo.get_all(order_by=[Role.name])
        return [RoleOut.model_validate(r) for r in roles]

    async def create_user(
        self,
        username: str,
        password: str,
        role_name: str,
        must_change_password: bool = False,
    ) -> UserOut:
        username = username.strip()
        if not username or not password:
            raise BadRequestException("Login i hasło są wymagane")

        role = await self._role(role_name)

        if await self.repo.get_by_username(username):
            raise BadRequestException("Użytkownik o tym loginie już istnieje")

        user = await self.repo.create_one(
            {
                "username": username,
                "hashed_password": hash_password(password),
                "role_uuid": role.uuid,
                "is_active": True,
                "must_change_password": must_change_password,
            }
        )
        return _user_out(user, role.name)

    async def update_user(
        self,
        user_uuid: UUID,
        username: str | None = None,
        password: str | None = None,
        role_name: str | None = None,
        must_change_password: bool | None = None,
        is_active: bool | None = None,
    ) -> UserOut:
        user = await self.repo.get_with_role(user_uuid)
        if user is None:
            raise ObjectNotFoundException("Nie znaleziono użytkownika")

        update: dict = {}
        role_name_out = user.role.name

        if username is not None:
            username = username.strip()
            if not username:
                raise BadRequestException("Login nie może być pusty")
            if username != user.username:
                if await self.repo.get_by_username(username):
                    raise BadRequestException("Użytkownik o tym loginie już istnieje")
                update["username"] = username

        if password:
            update["hashed_password"] = hash_password(password)

        if role_name is not None:
            role = await self._role(role_name)
            update["role_uuid"] = role.uuid
            role_name_out = role.name

        if must_change_password is not None:
            update["must_change_password"] = must_change_password

        if is_active is not None:
            update["is_active"] = is_active

        if update:
            user = await self.repo.update_one(user_uuid, update)

        return _user_out(user, role_name_out)

    async def delete_user(self, user_uuid: UUID) -> None:
        if await self.repo.get_one(uuid=user_uuid) is None:
            raise ObjectNotFoundException("Nie znaleziono użytkownika")
        # TODO(phase 4): refuse when the user already has movements.
        await self.repo.delete_one(user_uuid)
