from sqlalchemy import JSON, Column, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin, UUIDMixin
from app.models.movement import MovementType

# JSONB in Postgres, plain JSON in the SQLite tests.
JsonData = JSON().with_variant(JSONB(), "postgresql")


class DataImport(BaseModel, UUIDMixin, TimestampMixin):
    """One import of outside data (a Transplaner file, a day of Saldo Palet).

    created_at is when it was imported; the movements it booked point at it.
    """

    __tablename__ = "imports"

    # "transplaner" / "saldo_palet"
    source = Column(String(30), nullable=False, index=True)
    file_name = Column(String(255))
    user_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("users.uuid", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # What it booked, per operation (for the history list).
    summary = Column(JsonData)

    user = relationship("User")


class ImportDay(BaseModel, UUIDMixin, TimestampMixin):
    """What has been booked so far from a source for one day, operation and
    carrier type. A later file with other numbers books only the difference."""

    __tablename__ = "import_days"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "carrier_type_uuid",
            "movement_type",
            "day",
            name="uq_import_days_source_type_kind_day",
        ),
    )

    source = Column(String(30), nullable=False)
    carrier_type_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("carrier_types.uuid", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    movement_type = Column(
        SQLEnum(MovementType, native_enum=False, length=30), nullable=False
    )
    # The day the source gives (e.g. the day a store sent the pallets).
    day = Column(Date, nullable=False, index=True)
    # The quantity from the source, positive.
    quantity = Column(Integer, nullable=False)
