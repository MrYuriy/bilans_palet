from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class CarrierTypeRef(BaseModel):
    uuid: UUID
    name: str
    count_in_reports: bool

    model_config = {"from_attributes": True}


class GroupRef(BaseModel):
    uuid: UUID
    name: str

    model_config = {"from_attributes": True}


class StockRow(BaseModel):
    carrier_type: CarrierTypeRef
    quantity: int


class GroupStock(BaseModel):
    group: GroupRef
    rows: list[StockRow]
    # Sum of the rows shown.
    total: int


class CurrentBalanceOut(BaseModel):
    """What is in stock now, per carrier group and type (the types picked; by
    default those counted in reports)."""

    groups: list[GroupStock]


class DayValues(BaseModel):
    """closing = opening + receipts - shipments + corrections + reclassifications.
    Corrections include stock counts."""

    opening: int = 0
    receipts: int = 0
    shipments: int = 0
    corrections: int = 0
    reclassifications: int = 0
    closing: int = 0


class DayRowOut(DayValues):
    carrier_type: CarrierTypeRef


class GroupDay(BaseModel):
    group: GroupRef
    rows: list[DayRowOut]
    # Sum of the rows shown.
    total: DayValues


class HistoryPoint(BaseModel):
    day: date
    # Stock at the end of the day (the current day: so far).
    quantity: int


class HistoryOut(BaseModel):
    """The stock of the picked types day by day, oldest first."""

    days: list[HistoryPoint]


class DailyBalanceOut(BaseModel):
    day: date
    # A closed day shows its stored balance; an open one is a live preview.
    closed: bool
    closed_at: datetime | None
    groups: list[GroupDay]
