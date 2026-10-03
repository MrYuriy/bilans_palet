from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin, UUIDMixin


class MovementType(StrEnum):
    RECEIPT = "RECEIPT"  # Przyjęcie na magazyn: +
    LM_PURCHASE = "LM_PURCHASE"  # Zakup LM: a delivery by LM, counted like a receipt: +
    SHIPMENT = "SHIPMENT"  # Wysyłka z magazynu: -
    CORRECTION = "CORRECTION"  # Korekta: + or -
    RECLASSIFICATION = "RECLASSIFICATION"  # Przeksięgowanie: - better, + worse
    INVENTORY = "INVENTORY"  # Inwentaryzacja: counted - system, with the count sheet


class Movement(BaseModel, UUIDMixin, TimestampMixin):
    """One movement document entered for an area. Never edited after saving:
    a mistake is fixed with a correction."""

    __tablename__ = "movements"

    # Stored as plain text (not a Postgres enum), so a new type needs no migration.
    type = Column(
        SQLEnum(MovementType, native_enum=False, length=30),
        nullable=False,
        index=True,
    )
    area_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("areas.uuid", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("users.uuid", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    operation_date = Column(Date, nullable=False, index=True)
    document_number = Column(String(100))
    comment = Column(Text)

    area = relationship("Area")
    user = relationship("User")
    lines = relationship(
        "MovementLine",
        back_populates="movement",
        cascade="all, delete-orphan",
        order_by="MovementLine.position",
    )
    # Inventory only: the count sheet behind the movement's lines.
    inventory_lines = relationship(
        "InventoryLine",
        back_populates="movement",
        cascade="all, delete-orphan",
        order_by="InventoryLine.position",
    )


class MovementLine(BaseModel, UUIDMixin, TimestampMixin):
    """A line of a movement: how much the area's balance of one pallet type and
    quality changes. The quantity carries the sign, so a balance is a plain sum."""

    __tablename__ = "movement_lines"
    __table_args__ = (
        CheckConstraint("quantity <> 0", name="ck_movement_lines_quantity_nonzero"),
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
    quantity = Column(Integer, nullable=False)

    movement = relationship("Movement", back_populates="lines")
    pallet_type = relationship("PalletType")
    quality = relationship("Quality")
