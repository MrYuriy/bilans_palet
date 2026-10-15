from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.models.movement import MovementType
from app.schemas.common import NamedRef
from app.schemas.movement import UserRef


class DayChange(BaseModel):
    day: date
    # In the file now / booked from earlier files.
    in_file: int
    booked: int


class ImportKindOut(BaseModel):
    """One operation an import books (e.g. shipments to the stores)."""

    type: MovementType
    label: str
    # Sum of the month in the file, and what earlier files already booked.
    in_file: int
    booked: int
    # Signed change of the stock this import makes (0: nothing new).
    change: int
    days: list[DayChange]


class TransplanerPreviewOut(BaseModel):
    carrier: str
    carrier_type: NamedRef
    month: date
    # Recipients with any quantity, and the last day with one.
    recipients: int
    last_day: date | None
    kinds: list[ImportKindOut]
    warnings: list[str]


class ImportOut(BaseModel):
    uuid: UUID
    source: str
    file_name: str | None
    user: UserRef
    created_at: datetime
    summary: dict[str, Any] | None

    model_config = {"from_attributes": True}
