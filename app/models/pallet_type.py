from sqlalchemy import Boolean, Column, String, text

from app.models.base import BaseModel, TimestampMixin, UUIDMixin


class PalletType(BaseModel, UUIDMixin, TimestampMixin):
    """Pallet type, e.g. EUR. The admin can add more."""

    __tablename__ = "pallet_types"

    name = Column(String(50), nullable=False, unique=True)
    description = Column(String(255))
    is_active = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
