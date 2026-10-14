from uuid import UUID

from sqlalchemy import exists, select

from app.core.exc import (
    BadRequestException,
    ObjectAlreadyExistsException,
    ObjectNotFoundException,
)
from app.core.security import hash_password
from app.models.movement import Movement
from app.models.role import Role
from app.models.user import User
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.user import RoleOut, UserOut
from app.services.audit_service import AuditService


def _audit_view(out: UserOut, password_changed: bool = False) -> dict:
    """What the audit log keeps about a user; never the password hash."""
    view = {
        "username": out.username,
        "role": out.role,
        "is_active": out.is_active,
        "must_change_password": out.must_change_password,
    }
    if password_changed:
        view["password_changed"] = True
    return view


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
        self.audit = AuditService(session)

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
        actor: User,
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
        out = _user_out(user, role.name)
        await self.audit.log(
            actor, "create", "user", user.uuid, out.username, new_data=_audit_view(out)
        )
        return out

    async def update_user(
        self,
        actor: User,
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

        before = _audit_view(_user_out(user, user.role.name))
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

        out = _user_out(user, role_name_out)
        after = _audit_view(out, password_changed="hashed_password" in update)
        await self.audit.log_update(
            actor, "user", user.uuid, out.username, before, after
        )
        return out

    async def delete_user(self, actor: User, user_uuid: UUID) -> None:
        user = await self.repo.get_with_role(user_uuid)
        if user is None:
            raise ObjectNotFoundException("Nie znaleziono użytkownika")
        has_movements = await self.repo.session.execute(
            select(exists().where(Movement.user_uuid == user_uuid))
        )
        if has_movements.scalar_one():
            raise ObjectAlreadyExistsException(
                "Użytkownik ma zarejestrowane ruchy. Możesz go dezaktywować."
            )
        await self.audit.log(
            actor,
            "delete",
            "user",
            user.uuid,
            user.username,
            old_data=_audit_view(_user_out(user, user.role.name)),
        )
        await self.repo.delete_one(user_uuid)
