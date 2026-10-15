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
    """Stored codes; labels, signs and who may enter each live in
    app.services.operation_catalog."""

    PRODUCER_RECEIPT = "PRODUCER_RECEIPT"  # Przyjęcie od producentów EURO: +
    PRODUCER_SHIPMENT = "PRODUCER_SHIPMENT"  # Wysyłka do producentów EURO: -
    ECOM_TRANSFER = "ECOM_TRANSFER"  # Przesunięcie na ECOM: -
    OTHER_RECEIPT = "OTHER_RECEIPT"  # Inne — przyjęcie: +
    OTHER_SHIPMENT = "OTHER_SHIPMENT"  # Inne — wydanie: -
    # Booked from the Transplaner file, never entered by hand.
    STORE_SHIPMENT = "STORE_SHIPMENT"  # Wysyłka do sklepów: -
    STORE_RETURN = "STORE_RETURN"  # Zwroty ze sklepów: +
    UKR_SHIPMENT = "UKR_SHIPMENT"  # Wysyłka UKR: -
    UKR_RETURN = "UKR_RETURN"  # Zwroty z UKR: +
    # Booked from Saldo Palet each morning: IN - OUT - corrections, per type.
    SALDO_RECEIPT = "SALDO_RECEIPT"  # Przyjęcia (Saldo Palet): +/-
    CORRECTION = "CORRECTION"  # Korekta stanu: + or -
    RECLASSIFICATION = "RECLASSIFICATION"  # Przeksięgowanie: - from, + to
    INVENTORY = "INVENTORY"  # Inwentaryzacja: counted - system, with the count sheet


class Movement(BaseModel, UUIDMixin, TimestampMixin):
    """One movement document. Never edited after saving: a mistake is fixed
    with a correction."""

    __tablename__ = "movements"

    # Stored as plain text (not a Postgres enum), so a new type needs no migration.
    type = Column(
        SQLEnum(MovementType, native_enum=False, length=30),
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
    # Set when the movement was booked by an import (Transplaner, Saldo Palet).
    import_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("imports.uuid", ondelete="RESTRICT"),
        index=True,
    )

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
    """A line of a movement: how much the stock of one carrier type changes.
    The quantity carries the sign, so a balance is a plain sum."""

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
    carrier_type_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("carrier_types.uuid", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity = Column(Integer, nullable=False)

    movement = relationship("Movement", back_populates="lines")
    carrier_type = relationship("CarrierType")
