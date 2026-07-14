import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_ENV: str = "production"
    HOST: str = "0.0.0.0"  # nosec B104 — intentional: server must bind all interfaces
    PORT: int = 8000

    # Database individual fields (used when DATABASE_URL is not set directly)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "tododb"
    DB_USER: str = "todoapp"
    DB_PASSWORD: str = "changeme"

    # Optional direct URL override — when set (e.g. in tests via env var),
    # this takes priority over the computed postgresql+asyncpg:// URL.
    DATABASE_URL: Optional[str] = None

    @property
    def database_url(self) -> str:
        """
        Returns DATABASE_URL env var if set, otherwise builds the Postgres URL.
        Tests set DATABASE_URL=sqlite+aiosqlite:///:memory: so this returns SQLite.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Synchronous URL used by Alembic migrations."""
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
