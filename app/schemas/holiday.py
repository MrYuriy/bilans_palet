from datetime import date
from uuid import UUID

from pydantic import BaseModel


class HolidayCreate(BaseModel):
    day: date
    name: str = ""


class HolidayOut(BaseModel):
    uuid: UUID
    day: date
    name: str

    model_config = {"from_attributes": True}
