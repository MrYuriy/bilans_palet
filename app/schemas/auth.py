from uuid import UUID

from pydantic import BaseModel


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
    permissions: list[str] = []
    must_change_password: bool = False


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: CurrentUser
