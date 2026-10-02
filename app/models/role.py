from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin, UUIDMixin


class Role(BaseModel, UUIDMixin, TimestampMixin):
    __tablename__ = "roles"

    name = Column(String(50), nullable=False, unique=True)
    description = Column(String(255))

    users = relationship("User", back_populates="role")
