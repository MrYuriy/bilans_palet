from datetime import time

from sqlalchemy import CheckConstraint, Column, Integer, Time, text

from app.models.base import BaseModel, TimestampMixin

DEFAULT_DAY_CUTOFF = time(6, 0)


class SystemSettings(BaseModel, TimestampMixin):
    """System-wide settings the admin changes. Exactly one row (id = 1)."""

    __tablename__ = "system_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_system_settings_single_row"),)

    id = Column(Integer, primary_key=True, default=1)

    # Warehouse day boundary: a day runs from this hour to the same hour next day,
    # and is closed when it ends (e.g. 06:00: a movement at 03:00 belongs to the
    # previous day).
    day_cutoff = Column(
        Time, nullable=False, default=DEFAULT_DAY_CUTOFF, server_default=text("'06:00'")
    )

    def __repr__(self):
        return f"<SystemSettings(day_cutoff={self.day_cutoff})>"
