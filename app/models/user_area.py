from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base

# Which areas (obszary) a user may work in; assigned by the admin.
# Deleting a user or an area removes its assignments.
user_areas = Table(
    "user_areas",
    Base.metadata,
    Column(
        "user_uuid",
        UUID(as_uuid=True),
        ForeignKey("users.uuid", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "area_uuid",
        UUID(as_uuid=True),
        ForeignKey("areas.uuid", ondelete="CASCADE"),
        primary_key=True,
    ),
)
