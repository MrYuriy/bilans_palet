from sqlalchemy import Boolean, Column, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin, UUIDMixin


class User(BaseModel, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    username = Column(String(100), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    # Forces a password change on next login (e.g. a password set by the admin).
    must_change_password = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    role_uuid = Column(UUID(as_uuid=True), ForeignKey("roles.uuid"), nullable=False)

    role = relationship("Role", back_populates="users")

    # Areas the admin assigned; one → used automatically, several → the user picks.
    areas = relationship(
        "Area",
        secondary="user_areas",
        order_by="Area.name",
        passive_deletes=True,
    )
