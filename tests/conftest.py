import os
from collections.abc import AsyncGenerator

# Settings are read at import time; tests must not depend on a local .env.
# The real database is never used: get_session is overridden with SQLite below.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.database.session import get_session
from app.main import app
from app.models.base import Base
from app.models.role import Role
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
    async def override_get_session():
        yield session

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
