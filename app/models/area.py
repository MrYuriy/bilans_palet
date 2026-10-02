from sqlalchemy import Boolean, Column, String, text

from app.models.base import BaseModel, TimestampMixin, UUIDMixin


class Area(BaseModel, UUIDMixin, TimestampMixin):
    """Obszar — a part of the warehouse with its own pallet balance."""

    __tablename__ = "areas"

    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(255))
    is_active = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
