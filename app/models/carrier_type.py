from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin, UUIDMixin


class CarrierType(BaseModel, UUIDMixin, TimestampMixin):
    """A carrier type the stock is kept for, e.g. EURO or EURO uszkodzone.

    Each type has its own balance. Reports count only the types marked
    ``count_in_reports`` (e.g. plain EURO); the others are shown on demand.
    """

    __tablename__ = "carrier_types"

    group_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("carrier_groups.uuid", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name = Column(String(50), nullable=False, unique=True)
    description = Column(String(255))
    # Order within the group (lists, report rows).
    sort_order = Column(Integer, nullable=False, default=0, server_default=text("0"))
    # The carrier's name in the Transplaner file (cell A1, e.g. "PAL EUR/ EPAL"):
    # its shipments and returns are booked on this type.
    transplaner_name = Column(String(100), unique=True)
    count_in_reports = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    is_active = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    group = relationship("CarrierGroup", back_populates="types")
