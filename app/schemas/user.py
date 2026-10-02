from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.area import AreaRef


class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    must_change_password: bool = False
    # Areas the user may work in.
    areas: list[UUID] = Field(default_factory=list)


class UserUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    role: str | None = None
    must_change_password: bool | None = None
    is_active: bool | None = None
    # None keeps the current areas; a list (also empty) replaces them.
    areas: list[UUID] | None = None


class UserOut(BaseModel):
    uuid: UUID
    username: str
    role: str
    is_active: bool
    must_change_password: bool = False
    areas: list[AreaRef] = Field(default_factory=list)


class RoleOut(BaseModel):
    uuid: UUID
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}
