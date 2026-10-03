from datetime import date, time

from pydantic import BaseModel


class SettingsOut(BaseModel):
    # "HH:MM": the hour a warehouse day ends and the next one starts.
    day_cutoff: str
    # The warehouse day it is now.
    current_day: date
    # The latest closed warehouse day (the D-1 report), None before the first.
    last_closed_day: date | None = None


class SettingsUpdate(BaseModel):
    day_cutoff: time
