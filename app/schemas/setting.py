from datetime import date, time

from pydantic import BaseModel, Field


class SettingsOut(BaseModel):
    # "HH:MM": the hour a warehouse day ends and the next one starts.
    day_cutoff: str
    # The warehouse day it is now.
    current_day: date
    # The latest closed warehouse day (the D-1 report), None before the first.
    last_closed_day: date | None = None
    # Most one line of a limited operation may carry.
    max_line_quantity: int


class SettingsUpdate(BaseModel):
    """Only what is given changes."""

    day_cutoff: time | None = None
    max_line_quantity: int | None = Field(default=None, ge=1, le=1_000_000)
