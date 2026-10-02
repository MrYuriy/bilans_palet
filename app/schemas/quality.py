from uuid import UUID

from pydantic import BaseModel, Field


class QualityCreate(BaseModel):
    name: str
    sort_order: int = Field(gt=0)
    description: str | None = None


class QualityUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = Field(default=None, gt=0)
    description: str | None = None
    is_active: bool | None = None


class QualityOut(BaseModel):
    uuid: UUID
    name: str
    sort_order: int
    description: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}
