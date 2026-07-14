from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Read the URL at import time (conftest patches settings before importing this
# module, so in tests this will be the SQLite URL, not the Postgres URL).
_url = settings.DATABASE_URL

# SQLite (used in CI/tests via aiosqlite) does not support pool_size,
# max_overflow or pool_pre_ping — pass those kwargs only for Postgres.
_is_sqlite = _url.startswith("sqlite")

_engine_kwargs: dict = {"echo": settings.APP_ENV == "development"}
if not _is_sqlite:
    _engine_kwargs.update(
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
else:
    # StaticPool keeps the same in-memory DB across connections (for tests).
    from sqlalchemy.pool import StaticPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool

engine = create_async_engine(_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
