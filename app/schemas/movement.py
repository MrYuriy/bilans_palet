from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.movement import MovementType
from app.schemas.common import NamedRef

# Shown in the UI.
MOVEMENT_LABELS: dict[MovementType, str] = {
    MovementType.RECEIPT: "Przyjęcie na magazyn",
    MovementType.LM_PURCHASE: "Zakup LM",
    MovementType.SHIPMENT: "Wysyłka z magazynu",
    MovementType.CORRECTION: "Korekta",
    MovementType.RECLASSIFICATION: "Przeksięgowanie kategorii",
}


class MovementTypeOut(BaseModel):
    code: MovementType
    label: str


class MovementLineIn(BaseModel):
    pallet_type_uuid: UUID
    quality_uuid: UUID
    # Always positive, except a correction, where the sign says + or -.
    quantity: int
    # Re-classification only: the worse quality the pallets move to
    # (quality_uuid is then the quality they leave).
    to_quality_uuid: UUID | None = None


class MovementCreate(BaseModel):
    type: MovementType
    # May be left out when the user has exactly one area.
    area_uuid: UUID | None = None
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
    pallet_type: NamedRef
    quality: NamedRef
    # Signed change of the area's balance.
    quantity: int

    model_config = {"from_attributes": True}


class MovementOut(BaseModel):
    uuid: UUID
    type: MovementType
    type_label: str
    area: NamedRef
    user: UserRef
    operation_date: date
    document_number: str | None
    comment: str | None
    created_at: datetime
    lines: list[MovementLineOut]
