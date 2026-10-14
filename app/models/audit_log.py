from sqlalchemy import JSON, BigInteger, Column, ForeignKey, Identity, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin, UUIDMixin

# JSONB in Postgres, plain JSON in the SQLite tests.
JsonData = JSON().with_variant(JSONB(), "postgresql")


class AuditLog(BaseModel, UUIDMixin, TimestampMixin):
    """Who changed what in users and dictionaries, and how. Never edited.

    Movements are not logged here: they are never edited and carry their author
    and time themselves.
    """

    __tablename__ = "audit_logs"

    # Insertion order: entries written in the same instant still list in the
    # order they happened (the clock alone can tie).
    seq = Column(BigInteger, Identity(), nullable=False, unique=True, index=True)

    # SET NULL keeps the entry when the user is deleted; username keeps it readable.
    user_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey("users.uuid", ondelete="SET NULL"),
        index=True,
    )
    username = Column(String(100), nullable=False)

    action = Column(String(20), nullable=False)  # create / update / delete
    entity = Column(String(50), nullable=False, index=True)  # user, carrier_type, ...
    # No foreign key: the row may be deleted later, the entry stays.
    entity_uuid = Column(UUID(as_uuid=True), nullable=False, index=True)
    entity_name = Column(String(255), nullable=False)

    old_data = Column(JsonData)
    new_data = Column(JsonData)

    user = relationship("User")
