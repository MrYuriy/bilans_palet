from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exc import BadRequestException, ForbiddenException
from app.core.jwt import create_access_token
from app.core.security import hash_password, needs_rehash, verify_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.area import AreaRef
from app.schemas.auth import CurrentUser, LoginResponse
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService

# Verified against when the username does not exist, so a login attempt takes
# the same time whether or not the account exists.
_DUMMY_HASH = hash_password("dummy-password")


class AuthService:
    def __init__(self, session: AsyncSession):
        self.repo = UserRepository(session)
        self.permissions = PermissionService()
        self.audit = AuditService(session)

    def current_user(self, user: User) -> CurrentUser:
        return CurrentUser(
            uuid=user.uuid,
            username=user.username,
            is_active=user.is_active,
            role=user.role.name,
            permissions=self.permissions.allowed_modules(user.role.name),
            must_change_password=user.must_change_password,
            areas=[
                AreaRef.model_validate(a)
                for a in sorted(user.areas, key=lambda a: a.name)
                if a.is_active
            ],
        )

    async def login(self, username: str, password: str) -> LoginResponse | None:
        user = await self.repo.get_by_username(username.strip())

        if user is None:
            verify_password(password, _DUMMY_HASH)
            return None

        if not verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            raise ForbiddenException("Konto jest nieaktywne")

        if needs_rehash(user.hashed_password):
            await self.repo.update_one(
                user.uuid, {"hashed_password": hash_password(password)}
            )

        token = create_access_token({"sub": str(user.uuid)})
        return LoginResponse(access_token=token, user=self.current_user(user))

    async def change_password(
        self, user: User, old_password: str, new_password: str
    ) -> None:
        if not verify_password(old_password, user.hashed_password):
            raise BadRequestException("Nieprawidłowe obecne hasło")
        if not new_password:
            raise BadRequestException("Nowe hasło jest wymagane")

        before = {"must_change_password": user.must_change_password}
        await self.repo.update_one(
            user.uuid,
            {
                "hashed_password": hash_password(new_password),
                "must_change_password": False,
            },
        )
        await self.audit.log_update(
            user,
            "user",
            user.uuid,
            user.username,
            before,
            {"must_change_password": False, "password_changed": True},
        )
