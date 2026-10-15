from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import NamedRef


class CarrierGroupCreate(BaseModel):
    name: str
    description: str | None = None


class CarrierGroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class CarrierGroupOut(BaseModel):
    uuid: UUID
    name: str
    description: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class CarrierTypeCreate(BaseModel):
    group_uuid: UUID
    name: str
    description: str | None = None
    sort_order: int = 0
    count_in_reports: bool = True
    transplaner_name: str | None = None
    saldo_palet_unit: str | None = None


class CarrierTypeUpdate(BaseModel):
    group_uuid: UUID | None = None
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None
    count_in_reports: bool | None = None
    transplaner_name: str | None = None
    saldo_palet_unit: str | None = None
    is_active: bool | None = None


class CarrierTypeOut(BaseModel):
    uuid: UUID
    group: NamedRef
    name: str
    description: str | None = None
    sort_order: int
    count_in_reports: bool
    # Its name in the Transplaner file (cell A1), if its numbers come from there.
    transplaner_name: str | None = None
    saldo_palet_unit: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}
