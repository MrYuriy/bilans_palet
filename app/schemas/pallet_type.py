from uuid import UUID

from pydantic import BaseModel


class PalletTypeCreate(BaseModel):
    name: str
    description: str | None = None


class PalletTypeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class PalletTypeOut(BaseModel):
    uuid: UUID
    name: str
    description: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}
