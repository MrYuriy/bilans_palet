from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import NamedRef


class StockRow(BaseModel):
    pallet_type: NamedRef
    quality: NamedRef
    quantity: int


class AreaStock(BaseModel):
    area: NamedRef
    rows: list[StockRow]


class CurrentBalanceOut(BaseModel):
    """What is in stock now: per area, and all of them together."""

    areas: list[AreaStock]
    total: list[StockRow]


class DayRowOut(BaseModel):
    """One pallet type and quality of a warehouse day.

    closing = opening + receipts - shipments + corrections + reclassifications.
    Receipts include LM purchases; corrections include stock counts.
    """

    pallet_type: NamedRef
    quality: NamedRef
    opening: int
    receipts: int
    shipments: int
    corrections: int
    reclassifications: int
    closing: int


class AreaDay(BaseModel):
    area: NamedRef
    rows: list[DayRowOut]


class DailyBalanceOut(BaseModel):
    day: date
    # A closed day shows its stored balance; an open one is a live preview.
    closed: bool
    closed_at: datetime | None
    areas: list[AreaDay]
    total: list[DayRowOut]
