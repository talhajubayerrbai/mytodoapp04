"""
Shared pytest fixtures — SQLite in-memory, no PostgreSQL needed in CI.

How it works:
  1. DATABASE_URL is set to sqlite+aiosqlite:///:memory: BEFORE any app import.
     pydantic-settings reads it as the Settings.DATABASE_URL field, so
     settings.database_url returns the SQLite URL everywhere in the app.
  2. app/database.py detects "sqlite" in the URL and creates a StaticPool
     engine — all connections share the same in-memory database.
  3. Each test gets a fresh client with get_db overridden to use the test
     session factory. clean_db truncates the todos table before each test.
  4. No monkey-patching of app internals needed.
"""
import os

# ── 1. Force SQLite URL BEFORE any app import ─────────────────────────────────
#    Settings.DATABASE_URL field takes priority over the computed Postgres URL.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["APP_ENV"] = "test"

# ── 2. Now safe to import app modules ─────────────────────────────────────────
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker   # noqa: E402
from sqlalchemy.pool import StaticPool                                 # noqa: E402

import pytest                                                          # noqa: E402
import pytest_asyncio                                                  # noqa: E402
from sqlalchemy import text                                            # noqa: E402
from httpx import AsyncClient, ASGITransport                           # noqa: E402

from app.database import engine, Base, get_db, AsyncSessionLocal      # noqa: E402
from app.main import app                                               # noqa: E402

# Test session factory — same engine as the app (StaticPool in-memory SQLite)
_test_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ─────────────────────────────────────────────────────────────────────────────
# SESSION-SCOPED: create tables once for the whole test run
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ─────────────────────────────────────────────────────────────────────────────
# PER-TEST: clean slate before each test
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture()
async def clean_db():
    """Truncate todos table before every test for full isolation."""
    async with _test_session_factory() as session:
        await session.execute(text("DELETE FROM todos"))
        await session.commit()
    yield


@pytest_asyncio.fixture()
async def db_session():
    """
    A fresh AsyncSession for direct DB assertions in tests.
    Shares the same StaticPool engine — sees all data written via HTTP client.
    """
    async with _test_session_factory() as session:
        yield session


@pytest_asyncio.fixture()
async def client(clean_db):
    """
    httpx AsyncClient backed by the FastAPI ASGI app.
    Overrides get_db with a test session so HTTP requests land in the same
    StaticPool in-memory database as db_session.
    clean_db is included here so the DB is always clean before client is used.
    """
    async def _override_get_db():
        async with _test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
