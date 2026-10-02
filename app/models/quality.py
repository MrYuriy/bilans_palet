from sqlalchemy import Boolean, Column, Integer, String, text

from app.models.base import BaseModel, TimestampMixin, UUIDMixin


class Quality(BaseModel, UUIDMixin, TimestampMixin):
    """Pallet quality (I, II, III, ...), shared by all pallet types.

    ``sort_order`` ranks qualities from best (1) to worst; it orders lists and
    decides which way a re-classification may go (only to a worse quality).
    """

    __tablename__ = "qualities"

    name = Column(String(20), nullable=False, unique=True)
    sort_order = Column(Integer, nullable=False, unique=True)
    description = Column(String(255))
    is_active = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
