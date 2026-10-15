from datetime import date, time
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.movement import MovementType


class ReminderCreate(BaseModel):
    name: str
    check: str
    movement_type: MovementType | None = None
    deadline: time
    recipients: list[str] = Field(default_factory=list)
    is_active: bool = True


class ReminderUpdate(BaseModel):
    name: str | None = None
    check: str | None = None
    movement_type: MovementType | None = None
    deadline: time | None = None
    recipients: list[str] | None = None
    is_active: bool | None = None


class ReminderOut(BaseModel):
    uuid: UUID
    name: str
    check: str
    movement_type: MovementType | None
    # What it waits for, in Polish.
    description: str
    deadline: str  # HH:MM
    recipients: list[str]
    is_active: bool
    last_sent_on: date | None


class RemindersStatus(BaseModel):
    """Whether mail can go out at all, and whether today is checked."""

    smtp_configured: bool
    sender: str | None
    working_day_today: bool
    # What can be checked: code -> label.
    checks: dict[str, str]
