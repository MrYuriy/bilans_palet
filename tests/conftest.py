import os
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import date

# Settings are read at import time; tests must not depend on a local .env.
# The real database is never used: get_session is overridden with SQLite below.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.core.timeutils import business_date, local_now
from app.database.session import get_session
from app.main import app
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.carrier_group import CarrierGroup
from app.models.carrier_type import CarrierType
from app.models.role import Role
from app.models.setting import DEFAULT_DAY_CUTOFF
from app.models.user import User
from app.repositories.role_repo import RoleRepository

# In-memory SQLite; StaticPool keeps one connection so every session sees the
# same database within a test.
TEST_DATABASE_URL = "sqlite+aiosqlite://"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine.sync_engine, "connect")
def _enforce_foreign_keys(dbapi_connection, _record):
    # SQLite ignores foreign keys (and ON DELETE CASCADE) unless asked; Postgres
    # always enforces them, so the tests must too.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@event.listens_for(AuditLog, "before_insert")
def _number_audit_entry(_mapper, connection, entry):
    # Postgres numbers audit entries itself (identity column); SQLite cannot do
    # that for a column outside the primary key, so the tests do it here. The
    # last number is kept too, for several entries flushed together.
    last = max(
        connection.info.get("audit_seq", 0),
        connection.execute(select(func.max(AuditLog.seq))).scalar() or 0,
    )
    entry.seq = connection.info["audit_seq"] = last + 1


TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture
async def setup_database() -> AsyncGenerator[None, None]:
    """Create all tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(session) -> AsyncGenerator[AsyncClient, None]:
    # A fresh session per request, as in production: nothing cached by one request
    # (or by the test's own `session`) leaks into the next one.
    async def override_get_session():
        async with TestSessionLocal() as request_session:
            yield request_session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------- auth helpers ----------

PASSWORD = "Haslo123!"


async def make_user(
    session: AsyncSession,
    username: str,
    role: str = "operator",
    password: str = PASSWORD,
    **fields,
) -> User:
    """Create a user (and its role, if missing) directly in the database."""
    role_obj = await RoleRepository(session).get_by_name(role)
    if role_obj is None:
        role_obj = Role(name=role)
        session.add(role_obj)
        await session.flush()

    user = User(
        username=username,
        hashed_password=hash_password(password),
        role_uuid=role_obj.uuid,
        **fields,
    )
    session.add(user)
    await session.commit()
    return user


async def login(
    client: AsyncClient, username: str, password: str = PASSWORD
) -> dict[str, str]:
    """Log in through the API and return the Authorization header."""
    response = await client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture
async def admin_headers(client, session) -> dict[str, str]:
    """Authorization header of a freshly created admin user."""
    await make_user(session, "admin", role="admin")
    return await login(client, "admin")


def warehouse_today():
    """Today's warehouse day under the default cut-off (no settings row in tests)."""
    return business_date(local_now(), DEFAULT_DAY_CUTOFF)


# ---------- carriers and movements ----------


@dataclass
class Carriers:
    """uuids of the carrier groups and types most tests work with."""

    eur_group: str
    single_group: str
    euro: str  # EUR group, counted in reports
    damaged: str  # EUR group, not counted
    scrap: str  # EUR group, not counted
    single: str  # Jednorazowe group, counted
    inactive: str  # EUR group, inactive


@pytest_asyncio.fixture
async def carriers(session) -> Carriers:
    eur = CarrierGroup(name="EUR")
    single = CarrierGroup(name="Jednorazowe")
    session.add_all([eur, single])
    await session.flush()
    types = {
        "euro": CarrierType(group_uuid=eur.uuid, name="EURO", sort_order=1),
        "damaged": CarrierType(
            group_uuid=eur.uuid,
            name="EURO uszkodzone",
            sort_order=2,
            count_in_reports=False,
        ),
        "scrap": CarrierType(
            group_uuid=eur.uuid,
            name="EURO utylizacja",
            sort_order=3,
            count_in_reports=False,
        ),
        "single": CarrierType(group_uuid=single.uuid, name="Jednorazowe"),
        "inactive": CarrierType(
            group_uuid=eur.uuid, name="CHEP", sort_order=9, is_active=False
        ),
    }
    session.add_all(types.values())
    await session.commit()
    return Carriers(
        eur_group=str(eur.uuid),
        single_group=str(single.uuid),
        **{key: str(row.uuid) for key, row in types.items()},
    )


def line(carrier_type: str, quantity: int, to: str | None = None) -> dict:
    row = {"carrier_type_uuid": carrier_type, "quantity": quantity}
    if to is not None:
        row["to_carrier_type_uuid"] = to
    return row


async def move(
    client: AsyncClient,
    headers: dict[str, str],
    kind: str,
    *lines: dict,
    day: date | None = None,
    comment: str | None = "test",
    **fields,
):
    """POST a movement; returns the response (not checked)."""
    payload = {"type": kind, "comment": comment, "lines": list(lines), **fields}
    if day is not None:
        payload["operation_date"] = day.isoformat()
    return await client.post("/movements", headers=headers, json=payload)
