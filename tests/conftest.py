"""Shared test fixtures for API tests."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from api.database import Base, get_db
from api.limiter import limiter
from api.main import app

# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


def _reset_limiter_state() -> None:
    """Reset SlowAPI in-memory counters to avoid cross-test contamination."""
    storage = getattr(limiter, "_storage", None)
    if storage is None:
        return
    # limits >= 3 uses 'storage', 'expirations', 'events' in MemoryStorage
    if hasattr(storage, "storage"):
        storage.storage.clear()
    if hasattr(storage, "expirations"):
        storage.expirations.clear()
    if hasattr(storage, "events"):
        storage.events.clear()
    # Fallback for old limits versions
    cache = getattr(storage, "_cache", None)
    if isinstance(cache, dict):
        cache.clear()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables before each test, drop after, and reset rate limiter."""
    async with test_engine.begin() as conn:
        # Ensure foreign key enforcement is OFF so tests that set it ON
        # (e.g. test_cascade_delete_company_removes_users) don't leak
        # to subsequent tests and cause IntegrityError on loose FK refs.
        await conn.execute(text("PRAGMA foreign_keys=OFF"))
        await conn.run_sync(Base.metadata.create_all)
    # Disable rate limits for tests so they don't interfere
    _reset_limiter_state()
    limiter.enabled = False
    yield
    limiter.enabled = True
    _reset_limiter_state()
    async with test_engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=OFF"))
        await conn.run_sync(Base.metadata.drop_all)


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    """Client with a pre-registered and authenticated user."""
    # Register
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "Securepass123!",
        "full_name": "Test User",
        "company_name": "TestCorp",
        "industry": "manufacturing",
        "region": "US",
    })
    # Login
    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "Securepass123!",
    })
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
