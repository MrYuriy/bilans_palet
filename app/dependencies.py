from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exc import (
    BadRequestException,
    ForbiddenException,
    UnauthorizedException,
)
from app.core.jwt import decode_access_token
from app.database.session import get_session
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.permission_service import PermissionService
from app.services.saldo_palet_client import SaldoPaletClient, configured_client

# auto_error=False: a missing token is reported by us, in Polish.
security = HTTPBearer(auto_error=False)

permission_service = PermissionService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(security)]


async def get_current_user(credentials: CredentialsDep, session: SessionDep) -> User:
    """Resolve the authenticated user (role eager-loaded) from the JWT."""
    if credentials is None:
        raise UnauthorizedException("Brak autoryzacji")

    try:
        payload = decode_access_token(credentials.credentials)
        user_uuid = UUID(payload.get("sub"))
    except (JWTError, ValueError, TypeError) as e:
        # Bad signature/expired (JWTError), malformed or missing "sub" (ValueError/TypeError).
        raise UnauthorizedException("Sesja wygasła lub token jest nieprawidłowy") from e

    user = await UserRepository(session).get_with_role(user_uuid)

    if user is None:
        raise UnauthorizedException("Nie znaleziono użytkownika")

    if not user.is_active:
        raise ForbiddenException("Konto jest nieaktywne")

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_permission(module: str):
    """Dependency factory enforcing role access to a module at the API level.

    Use as ``Annotated[User, Depends(require_permission("module"))]``.
    """

    async def dependency(current_user: CurrentUserDep) -> User:
        if not permission_service.has_access(current_user.role.name, module):
            raise ForbiddenException("Brak uprawnień")
        return current_user

    return dependency


# Changing settings and days off — admin only.
SettingsAdmin = Annotated[User, Depends(require_permission("settings"))]

# Changing dictionaries (carrier groups and types) — admin only.
MasterdataAdmin = Annotated[User, Depends(require_permission("masterdata"))]


def get_saldo_palet_client() -> SaldoPaletClient:
    client = configured_client()
    if client is None:
        raise BadRequestException("Połączenie z Saldem Palet nie jest skonfigurowane")
    return client


SaldoPaletClientDep = Annotated[SaldoPaletClient, Depends(get_saldo_palet_client)]
