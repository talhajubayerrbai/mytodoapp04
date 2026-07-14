"""
Shared pytest fixtures — SQLite in-memory, no PostgreSQL needed in CI.

Architecture (clean session-per-test, no nested transactions):
  - SQLite env vars are force-set at module level BEFORE any app import.
  - app.config.Settings is monkey-patched at class level so DATABASE_URL
    returns the SQLite URL — meaning app.database.create_async_engine() sees
    SQLite, never Postgres, even in CI where DB_HOST etc. may already be set.
  - One shared test engine + session factory is built here, then swapped
    directly into app.database so all app code uses the same SQLite engine.
  - Each test gets ONE AsyncSession.  The session is simply closed on
    teardown (no rollback dance, no nested transaction) — isolation is
    achieved by DELETE in the clean_db fixture.
  - health.py and api.py call AsyncSessionLocal() directly (bypassing get_db).
    patch_db_sessions (autouse) replaces that reference in both routers so
    they receive the same session as the HTTP client.
"""
import os

# ── 1. Force SQLite env vars BEFORE any app import ───────────────────────────
#    Use assignment (not setdefault) so we override whatever CI already set.
os.environ["APP_ENV"]     = "test"
os.environ["DB_HOST"]     = "localhost"
os.environ["DB_PORT"]     = "5432"
os.environ["DB_NAME"]     = "testdb"
os.environ["DB_USER"]     = "testuser"
os.environ["DB_PASSWORD"] = "testpass"

# ── 2. Patch Settings class BEFORE app.database is imported ──────────────────
SQLITE_URL      = "sqlite+aiosqlite:///:memory:"
SQLITE_SYNC_URL = "sqlite:///test.db"

import app.config as _cfg_module  # noqa: E402

_cfg_module.Settings.DATABASE_URL      = property(lambda self: SQLITE_URL)       # type: ignore[assignment]
_cfg_module.Settings.DATABASE_URL_SYNC = property(lambda self: SQLITE_SYNC_URL)  # type: ignore[assignment]
_cfg_module.settings = _cfg_module.Settings()

# ── 3. Import app.database (now uses SQLite URL) ──────────────────────────────
import app.database as _db_module  # noqa: E402

import pytest                                              # noqa: E402
import pytest_asyncio                                     # noqa: E402
from contextlib import asynccontextmanager                # noqa: E402
from unittest.mock import patch                           # noqa: E402

from httpx import AsyncClient, ASGITransport              # noqa: E402
from sqlalchemy.ext.asyncio import (                      # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession,
)
from sqlalchemy.pool import StaticPool                    # noqa: E402
from sqlalchemy import text                               # noqa: E402

# ── 4. Build the shared test engine ──────────────────────────────────────────
#    StaticPool keeps the SAME in-memory database across all connections.
_test_engine = create_async_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
_test_session_factory = async_sessionmaker(
    bind=_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# ── 5. Swap app.database internals with test versions ────────────────────────
_db_module.engine            = _test_engine
_db_module.AsyncSessionLocal = _test_session_factory

# ── 6. Now safe to import the FastAPI app ────────────────────────────────────
from app.main import app         # noqa: E402
from app.database import Base, get_db  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# SESSION-SCOPED: create tables once for the whole test run
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ─────────────────────────────────────────────────────────────────────────────
# PER-TEST: one clean session, simply closed on teardown
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture()
async def db_session():
    """
    One AsyncSession per test.  No rollback gymnastics — we just close it.
    Isolation is handled by clean_db (DELETE at test start).
    """
    async with _test_session_factory() as session:
        yield session
        # Flush any pending state so teardown is clean; ignore errors.
        try:
            await session.commit()
        except Exception:
            await session.rollback()


@pytest_asyncio.fixture(autouse=True)
async def patch_db_sessions(db_session: AsyncSession):
    """
    health.py and api.py import AsyncSessionLocal directly and call it as
    an async context manager.  Patch all three locations to return the same
    shared session so data is visible across the client and those routers.
    """
    @asynccontextmanager
    async def _yield_same_session():
        yield db_session

    class _FakeSessionLocal:
        def __call__(self):
            return _yield_same_session()

    fake = _FakeSessionLocal()

    with (
        patch("app.routers.health.AsyncSessionLocal", fake),
        patch("app.routers.api.AsyncSessionLocal",    fake),
        patch("app.database.AsyncSessionLocal",       fake),
    ):
        yield


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession):
    """
    httpx AsyncClient backed by the FastAPI ASGI app.
    get_db is overridden to yield the shared db_session so HTTP requests
    and direct AsyncSessionLocal() calls all hit the same SQLite session.
    """
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def clean_db(db_session: AsyncSession):
    """
    Truncate all todos rows BEFORE each test that requests this fixture.
    Does NOT flush/rollback after — the per-test session teardown handles that.
    """
    await db_session.execute(text("DELETE FROM todos"))
    await db_session.commit()
    yield
