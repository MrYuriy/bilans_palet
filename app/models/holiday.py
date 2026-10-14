from sqlalchemy import Column, Date, String

from app.models.base import BaseModel, TimestampMixin, UUIDMixin


class Holiday(BaseModel, UUIDMixin, TimestampMixin):
    """A day off (public holiday or a day the admin adds). Weekends need no row.

    Reminders about missing data are not sent on these days.
    """

    __tablename__ = "holidays"

    day = Column(Date, nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
