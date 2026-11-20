from datetime import time

from sqlalchemy import CheckConstraint, Column, Integer, Time, text

from app.models.base import BaseModel, TimestampMixin

DEFAULT_DAY_CUTOFF = time(0, 0)
# Most a line of the limited operations may carry (see operation_catalog).
DEFAULT_MAX_LINE_QUANTITY = 700


class SystemSettings(BaseModel, TimestampMixin):
    """System-wide settings the admin changes. Exactly one row (id = 1)."""

    __tablename__ = "system_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_system_settings_single_row"),)

    id = Column(Integer, primary_key=True, default=1)

    # Warehouse day boundary: a day runs from this hour to the same hour next day,
    # and is closed when it ends. Midnight by default (the day ends at 23:59:59);
    # with 06:00 a movement at 03:00 would belong to the previous day.
    day_cutoff = Column(
        Time, nullable=False, default=DEFAULT_DAY_CUTOFF, server_default=text("'00:00'")
    )

    # One entry of a limited operation (to producers, to ECOM, other receipt or
    # shipment) carries at most this many of a carrier type; more is a typo.
    max_line_quantity = Column(
        Integer,
        CheckConstraint("max_line_quantity > 0", name="ck_system_settings_max_line"),
        nullable=False,
        default=DEFAULT_MAX_LINE_QUANTITY,
        server_default=text(str(DEFAULT_MAX_LINE_QUANTITY)),
    )

    def __repr__(self):
        return f"<SystemSettings(day_cutoff={self.day_cutoff})>"
