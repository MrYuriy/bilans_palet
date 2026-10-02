from fastapi import APIRouter

from app.core.exc import UnauthorizedException
from app.dependencies import CurrentUserDep, SessionDep
from app.schemas.auth import (
    ChangePasswordRequest,
    CurrentUser,
    LoginRequest,
    LoginResponse,
)
from app.schemas.common import ActionResult
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, session: SessionDep):
    result = await AuthService(session).login(payload.username, payload.password)
    if result is None:
        raise UnauthorizedException("Nieprawidłowy login lub hasło")
    await session.commit()
    return result


@router.get("/me", response_model=CurrentUser)
async def me(current_user: CurrentUserDep, session: SessionDep):
    """The current user and the modules they may use (for UI gating)."""
    return AuthService(session).current_user(current_user)


@router.post("/change-password", response_model=ActionResult)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUserDep,
    session: SessionDep,
):
    await AuthService(session).change_password(
        current_user, payload.old_password, payload.new_password
    )
    await session.commit()
    return ActionResult()
