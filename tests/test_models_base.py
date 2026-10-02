from uuid import UUID

from sqlalchemy import Column, String, select

from app.models.base import BaseModel, TimestampMixin, UUIDMixin


class Probe(BaseModel, UUIDMixin, TimestampMixin):
    """Test-only model: checks the shared mixins work on SQLite as well."""

    __tablename__ = "test_probe"

    name = Column(String(20))


async def test_mixins_fill_uuid_and_timestamps(session):
    probe = Probe(name="x")
    session.add(probe)
    await session.commit()

    stored = (await session.execute(select(Probe))).scalar_one()

    assert isinstance(stored.uuid, UUID)
    assert stored.created_at is not None
    assert stored.updated_at is not None
    assert stored.to_dict(exclude={"created_at", "updated_at"}) == {
        "name": "x",
        "uuid": stored.uuid,
    }
