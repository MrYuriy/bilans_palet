from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.area import AreaRef


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class CurrentUser(BaseModel):
    uuid: UUID
    username: str
    is_active: bool
    role: str
    permissions: list[str] = Field(default_factory=list)
    must_change_password: bool = False
    # Active areas the user may work in: one → used automatically, several → pick.
    areas: list[AreaRef] = Field(default_factory=list)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: CurrentUser
