from sqlalchemy import JSON, Boolean, Column, Date, String, Time, text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel, TimestampMixin, UUIDMixin
from app.models.movement import MovementType

# JSONB in Postgres, plain JSON in the SQLite tests.
JsonData = JSON().with_variant(JSONB(), "postgresql")


class Reminder(BaseModel, UUIDMixin, TimestampMixin):
    """Something the team must do each working day by a time (upload the
    Transplaner file, ...). If it is not done by then, a mail goes out."""

    __tablename__ = "reminders"

    name = Column(String(100), nullable=False, unique=True)
    # What counts as done today: "saldo_palet" (the import ran), "transplaner"
    # (a file was uploaded) or "movement" (a movement of movement_type).
    check = Column(String(30), nullable=False)
    movement_type = Column(SQLEnum(MovementType, native_enum=False, length=30))
    deadline = Column(Time, nullable=False)
    recipients = Column(JsonData, nullable=False, default=list)
    is_active = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    # The day it was last checked after its deadline: once a day at most.
    last_run_on = Column(Date)
    last_sent_on = Column(Date)
