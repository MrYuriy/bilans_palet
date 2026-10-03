from sqlalchemy import Column, Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin, UUIDMixin


class DayClosure(BaseModel, UUIDMixin, TimestampMixin):
    """A closed warehouse day. Once here, nothing can be entered for that day.

    created_at is when it was closed.
    """

    __tablename__ = "day_closures"

    business_date = Column(Date, nullable=False, unique=True, index=True)


class DailyBalance(BaseModel, UUIDMixin, TimestampMixin):
    """The balance of one closed warehouse day, for one area, pallet type and quality.

    Stored when the day closes and never changed afterwards. Receipts and
    shipments are positive counts; corrections (incl. stock counts) and
    re-classifications are signed. closing = opening + receipts - shipments
    + corrections + reclassifications.
    """

    __tablename__ = "daily_balances"
    __table_args__ = (
        UniqueConstraint(
            "business_date",
            "area_uuid",
            "pallet_type_uuid",
            "quality_uuid",
            name="uq_daily_balances_day_area_type_quality",
        ),
    )

    business_date = Column(Date, nullable=False, index=True)
    area_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("areas.uuid", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    pallet_type_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("pallet_types.uuid", ondelete="RESTRICT"),
        nullable=False,
    )
    quality_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("qualities.uuid", ondelete="RESTRICT"),
        nullable=False,
    )

    opening = Column(Integer, nullable=False)
    receipts = Column(Integer, nullable=False)
    shipments = Column(Integer, nullable=False)
    corrections = Column(Integer, nullable=False)
    reclassifications = Column(Integer, nullable=False)
    closing = Column(Integer, nullable=False)

    area = relationship("Area")
    pallet_type = relationship("PalletType")
    quality = relationship("Quality")
