from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.exc import ForbiddenException
from app.dependencies import SessionDep, require_permission
from app.models.user import User
from app.schemas.common import ActionResult
from app.schemas.user import RoleOut, UserCreate, UserOut, UserUpdate
from app.services.user_service import UserService

# Admin-only user management (the "users" permission module).
router = APIRouter(tags=["Users"])

UsersAdmin = Annotated[User, Depends(require_permission("users"))]


@router.get("/users", response_model=list[UserOut])
async def list_users(session: SessionDep, _: UsersAdmin):
    return await UserService(session).list_users()


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(session: SessionDep, _: UsersAdmin):
    return await UserService(session).list_roles()


@router.post("/users", response_model=UserOut)
async def create_user(payload: UserCreate, session: SessionDep, _: UsersAdmin):
    user = await UserService(session).create_user(
        payload.username, payload.password, payload.role, payload.must_change_password
    )
    await session.commit()
    return user


@router.put("/users/{user_uuid}", response_model=UserOut)
async def update_user(
    user_uuid: UUID,
    payload: UserUpdate,
    session: SessionDep,
    current_user: UsersAdmin,
):
    if user_uuid == current_user.uuid and payload.is_active is False:
        raise ForbiddenException("Nie możesz dezaktywować własnego konta")

    user = await UserService(session).update_user(
        user_uuid,
        payload.username,
        payload.password,
        payload.role,
        payload.must_change_password,
        payload.is_active,
    )
    await session.commit()
    return user


@router.delete("/users/{user_uuid}", response_model=ActionResult)
async def delete_user(user_uuid: UUID, session: SessionDep, current_user: UsersAdmin):
    if user_uuid == current_user.uuid:
        raise ForbiddenException("Nie możesz usunąć własnego konta")

    await UserService(session).delete_user(user_uuid)
    await session.commit()
    return ActionResult()
