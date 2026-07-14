"""
Shared pytest fixtures.

Uses an in-memory SQLite database (via aiosqlite) so no real PostgreSQL
instance is required during CI.

Key design decisions:
- DATABASE_URL env vars are patched in `pytest_configure` (before any app
  module is imported) so SQLAlchemy never tries to connect to Postgres.
- `patch_db_sessions` is a session-scoped autouse fixture that replaces
  `AsyncSessionLocal` inside `app.routers.health` and `app.routers.api`
  (those routers call it directly, bypassing the `get_db` dependency).
- Individual tests use the `client` fixture which also overrides the `get_db`
  FastAPI dependency with the per-test isolated session.
"""
import os
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from contextlib import asynccontextmanager

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# ── Patch env BEFORE any app module is imported ───────────────────────────────
# app/config.py reads DB_* at import time; point it at SQLite so
# create_async_engine() in app/database.py does not try to reach Postgres.

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "testdb")
os.environ.setdefault("DB_USER", "testuser")
os.environ.setdefault("DB_PASSWORD", "testpass")
os.environ.setdefault("APP_ENV", "test")

# Now it's safe to import app modules
from app.main import app          # noqa: E402
from app.database import Base, get_db  # noqa: E402

# ── In-memory SQLite engine (session-scoped) ──────────────────────────────────

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    _engine = create_async_engine(
        SQLITE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest_asyncio.fixture(scope="session")
def session_factory(engine):
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


# ── Per-test DB session with rollback isolation ───────────────────────────────

@pytest_asyncio.fixture()
async def db_session(engine, session_factory):
    """
    Yields an AsyncSession backed by SQLite that is rolled back after every
    test so tests don't pollute each other.
    """
    async with engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


# ── Patch AsyncSessionLocal used directly by health & api routers ─────────────

@pytest_asyncio.fixture(autouse=True)
async def patch_db_sessions(engine):
    """
    health.py and api.py call `AsyncSessionLocal()` directly rather than going
    through the FastAPI `get_db` dependency.  We replace it with a factory that
    returns a real SQLite session so those endpoints work in CI without Postgres.
    """
    _session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    @asynccontextmanager
    async def _fake_session_ctx():
        async with _session_factory() as session:
            yield session

    # AsyncSessionLocal is used as an async context manager in both routers
    class _FakeSessionLocal:
        def __call__(self):
            return _fake_session_ctx()

        def __aenter__(self):
            return _fake_session_ctx().__aenter__()

        def __aexit__(self, *args):
            return _fake_session_ctx().__aexit__(*args)

    fake = _FakeSessionLocal()

    with patch("app.routers.health.AsyncSessionLocal", fake), \
         patch("app.routers.api.AsyncSessionLocal", fake):
        yield


# ── AsyncClient wired to the FastAPI app ──────────────────────────────────────

@pytest_asyncio.fixture()
async def client(db_session):
    """
    Returns an httpx AsyncClient that talks to the FastAPI app and overrides
    the `get_db` dependency with the per-test isolated SQLite session.
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
