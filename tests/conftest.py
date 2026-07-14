"""
Shared pytest fixtures.

Uses an in-memory SQLite database (via aiosqlite) so no real PostgreSQL
instance is required during CI.

Key design decisions:
- os.environ overrides happen BEFORE any app module is imported so that
  app/config.py Settings() resolves DB_* to safe test values, and
  app/database.py builds a SQLite engine (not Postgres).
- app/database.py already guards against SQLite-incompatible pool kwargs.
- `patch_db_sessions` replaces AsyncSessionLocal inside health.py and api.py
  (those routers call it directly, bypassing the `get_db` dependency).
- `client` overrides the FastAPI `get_db` dependency with a per-test session.
"""
import os

# ── Patch env BEFORE any app module is imported ───────────────────────────────
# Must come before any `from app.*` so Settings() and create_async_engine()
# both see these values at module-load time.
os.environ["APP_ENV"] = "test"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5432"
os.environ["DB_NAME"] = "testdb"
os.environ["DB_USER"] = "testuser"
os.environ["DB_PASSWORD"] = "testpass"

# Override the computed DATABASE_URL so app/database.py uses SQLite directly.
# pydantic-settings reads individual DB_* fields and builds the URL via a
# @property, but we can force the engine URL by monkey-patching the settings
# object AFTER import — see patch block below.

import pytest                                                        # noqa: E402
import pytest_asyncio                                                # noqa: E402
from unittest.mock import patch                                      # noqa: E402
from contextlib import asynccontextmanager                           # noqa: E402

from httpx import AsyncClient, ASGITransport                        # noqa: E402
from sqlalchemy.ext.asyncio import (                                 # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession,
)

# ── SQLite engine (session-scoped, shared across the whole test run) ──────────
SQLITE_URL = "sqlite+aiosqlite:///:memory:"

# Build the test engine immediately so we can inject it before app imports.
_test_engine = create_async_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
_test_session_factory = async_sessionmaker(
    bind=_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# ── Patch app.config.settings and app.database BEFORE importing app.main ──────
# This ensures create_async_engine inside app/database.py uses SQLite.
with patch("app.config.settings") as _mock_settings:
    _mock_settings.APP_ENV = "test"
    _mock_settings.DATABASE_URL = SQLITE_URL
    _mock_settings.HOST = "0.0.0.0"
    _mock_settings.PORT = 8000

    # Now safe to import — database.py will read settings.DATABASE_URL == SQLite
    import app.database as _app_db                                   # noqa: E402

# Replace the module-level engine and session factory with our test versions
_app_db.engine = _test_engine
_app_db.AsyncSessionLocal = _test_session_factory

# Now import main (it imports from app.database which we've already patched)
from app.main import app                                             # noqa: E402
from app.database import Base, get_db                               # noqa: E402


# ── Create tables once per session ───────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── Expose engine and session_factory as fixtures ────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def engine():
    yield _test_engine


@pytest_asyncio.fixture(scope="session")
def session_factory():
    return _test_session_factory


# ── Per-test DB session with rollback isolation ───────────────────────────────

@pytest_asyncio.fixture()
async def db_session():
    """
    Yields an AsyncSession backed by SQLite, rolled back after every test
    to prevent test pollution.
    """
    async with _test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


# ── Patch AsyncSessionLocal used directly by health & api routers ─────────────

@pytest_asyncio.fixture(autouse=True)
async def patch_db_sessions():
    """
    health.py and api.py call AsyncSessionLocal() directly — bypassing get_db.
    Replace it in both routers AND in app.database with our SQLite factory.
    """
    @asynccontextmanager
    async def _sqlite_ctx():
        async with _test_session_factory() as session:
            yield session

    class _FakeSessionLocal:
        """Mimics async_sessionmaker: callable returning an async context manager."""
        def __call__(self):
            return _sqlite_ctx()

        def __aenter__(self):
            return _sqlite_ctx().__aenter__()

        def __aexit__(self, *args):
            return _sqlite_ctx().__aexit__(*args)

    fake = _FakeSessionLocal()

    with patch("app.routers.health.AsyncSessionLocal", fake), \
         patch("app.routers.api.AsyncSessionLocal", fake), \
         patch("app.database.AsyncSessionLocal", fake):
        yield


# ── AsyncClient wired to the FastAPI app ──────────────────────────────────────

@pytest_asyncio.fixture()
async def client(db_session):
    """
    Returns an httpx AsyncClient pointing at the FastAPI app.
    Overrides the `get_db` dependency with the per-test isolated SQLite session.
    """
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Convenience fixture: wipe all todos between tests ─────────────────────────

@pytest_asyncio.fixture()
async def clean_db(db_session):
    """Delete all todo rows before and after each test for isolation."""
    from sqlalchemy import text
    await db_session.execute(text("DELETE FROM todos"))
    await db_session.flush()
    yield
    await db_session.execute(text("DELETE FROM todos"))
    await db_session.flush()
