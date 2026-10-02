from uuid import uuid4

from sqlalchemy import Column, DateTime, func, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import declarative_base

from app.core.timeutils import local_now

Base = declarative_base()


class CreatedAtMixin:
    # Python-side default in local time (deterministic, independent of DB tz).
    created_at = Column(
        DateTime,
        default=local_now,
        server_default=func.now(),
        index=True,
    )


class UpdatedAtMixin:
    updated_at = Column(
        DateTime,
        default=local_now,
        server_default=func.now(),
        onupdate=local_now,
    )


class TimestampMixin(CreatedAtMixin, UpdatedAtMixin):
    pass


class UUIDMixin:
    uuid = Column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
        index=True,
    )


class BaseModel(Base):
    __abstract__ = True

    def to_dict(self, exclude: set | None = None) -> dict:
        exclude = exclude or set()
        return {
            c.name: getattr(self, c.name)
            for c in self.__table__.columns
            if c.name not in exclude
        }

    def __repr__(self):
        return f"<{self.__class__.__name__}(uuid={self.uuid})>"
