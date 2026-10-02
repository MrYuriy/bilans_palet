from uuid import UUID

from pydantic import BaseModel


class AreaCreate(BaseModel):
    name: str
    description: str | None = None


class AreaUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class AreaOut(BaseModel):
    uuid: UUID
    name: str
    description: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}
