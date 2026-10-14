from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.movement import MovementType
from app.schemas.common import NamedRef


class MovementTypeOut(BaseModel):
    """An operation as the UI needs it to build the form."""

    code: MovementType
    label: str
    # +1 adds, -1 takes away, 0: the lines carry the sign (correction) or it is
    # special (re-classification, inventory).
    sign: int
    note_required: bool
    counted_types_only: bool
    # May the current user enter it here (inventory goes through its own screen).
    can_enter: bool


class MovementLineIn(BaseModel):
    carrier_type_uuid: UUID
    # Always positive, except a correction, where the sign says + or -.
    quantity: int
    # Re-classification only: the carrier type the quantity moves to
    # (carrier_type_uuid is the one it leaves).
    to_carrier_type_uuid: UUID | None = None


class MovementCreate(BaseModel):
    type: MovementType
    # Today when left out.
    operation_date: date | None = None
    document_number: str | None = None
    comment: str | None = None
    lines: list[MovementLineIn]


class UserRef(BaseModel):
    uuid: UUID
    username: str

    model_config = {"from_attributes": True}


class MovementLineOut(BaseModel):
    carrier_type: NamedRef
    # Signed change of the stock.
    quantity: int

    model_config = {"from_attributes": True}


class InventoryLineOut(BaseModel):
    """A row of a count sheet: the system balance, what was counted, the difference."""

    carrier_type: NamedRef
    system_quantity: int
    counted_quantity: int
    difference: int


class MovementOut(BaseModel):
    uuid: UUID
    type: MovementType
    type_label: str
    user: UserRef
    operation_date: date
    document_number: str | None
    comment: str | None
    created_at: datetime
    lines: list[MovementLineOut]
    # Inventory only: the count sheet; None for other movements.
    inventory_lines: list[InventoryLineOut] | None = None


class InventoryLineIn(BaseModel):
    carrier_type_uuid: UUID
    counted_quantity: int


class InventoryCreate(BaseModel):
    """A stock count. Dated today; only the counted rows change."""

    document_number: str | None = None
    comment: str | None = None
    lines: list[InventoryLineIn]


class SheetRowOut(BaseModel):
    """A row of an empty count sheet: what the system holds now."""

    group: NamedRef
    carrier_type: NamedRef
    system_quantity: int
