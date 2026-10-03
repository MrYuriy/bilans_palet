from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin, UUIDMixin


class InventoryLine(BaseModel, UUIDMixin, TimestampMixin):
    """One row of a stock count sheet (arkusz spisu), kept as history.

    The inventory movement it belongs to carries only the non-zero differences
    (a movement line cannot be zero); the sheet keeps every counted row, so a
    count that confirmed the stock is recorded too.
    """

    __tablename__ = "inventory_lines"
    __table_args__ = (
        CheckConstraint(
            "counted_quantity >= 0", name="ck_inventory_lines_counted_not_negative"
        ),
    )

    movement_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("movements.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position = Column(Integer, nullable=False)
    pallet_type_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("pallet_types.uuid", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quality_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("qualities.uuid", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Balance in the system at the moment the count was approved.
    system_quantity = Column(Integer, nullable=False)
    counted_quantity = Column(Integer, nullable=False)

    movement = relationship("Movement", back_populates="inventory_lines")
    pallet_type = relationship("PalletType")
    quality = relationship("Quality")
