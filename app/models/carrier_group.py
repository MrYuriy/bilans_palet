from sqlalchemy import Boolean, Column, String, text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin, UUIDMixin


class CarrierGroup(BaseModel, UUIDMixin, TimestampMixin):
    """A group of carrier types counted together, e.g. EUR or Jednorazowe."""

    __tablename__ = "carrier_groups"

    name = Column(String(50), nullable=False, unique=True)
    description = Column(String(255))
    is_active = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    types = relationship("CarrierType", back_populates="group")
