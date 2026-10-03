from datetime import date, time

from pydantic import BaseModel


class SettingsOut(BaseModel):
    # "HH:MM": the hour a warehouse day ends and the next one starts.
    day_cutoff: str
    # The warehouse day it is now.
    current_day: date


class SettingsUpdate(BaseModel):
    day_cutoff: time
