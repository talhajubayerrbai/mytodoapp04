"""
Unit tests for app/config.py — Settings class and computed URL properties.
Uses monkeypatch / environment variable overrides; no real DB connection made.
"""
import pytest
from app.config import Settings


# ─── Settings defaults ────────────────────────────────────────────────────────

class TestSettingsDefaults:
    def test_default_app_env(self):
        # Pass APP_ENV explicitly so the env var set by conftest ("test") doesn't bleed in
        s = Settings(
            APP_ENV="production",
            DB_HOST="h", DB_PORT=5432, DB_NAME="n",
            DB_USER="u", DB_PASSWORD="p",
        )
        assert s.APP_ENV == "production"

    def test_default_host(self):
        s = Settings(
            DB_HOST="h", DB_PORT=5432, DB_NAME="n",
            DB_USER="u", DB_PASSWORD="p",
        )
        assert s.HOST == "0.0.0.0"

    def test_default_port(self):
        s = Settings(
            DB_HOST="h", DB_PORT=5432, DB_NAME="n",
            DB_USER="u", DB_PASSWORD="p",
        )
        assert s.PORT == 8000


# ─── DATABASE_URL property ────────────────────────────────────────────────────

class TestDatabaseURL:
    def _make(self, host="myhost", port=5432, name="mydb",
              user="myuser", password="mypass"):
        # Pass DATABASE_URL=None explicitly so pydantic-settings does NOT pick up
        # the DATABASE_URL=sqlite+aiosqlite:///:memory: set by conftest.py,
        # allowing us to test the computed postgresql+asyncpg:// URL.
        return Settings(
            DB_HOST=host, DB_PORT=port, DB_NAME=name,
            DB_USER=user, DB_PASSWORD=password,
            DATABASE_URL=None,
        )

    def test_uses_asyncpg_driver(self):
        s = self._make()
        assert s.database_url.startswith("postgresql+asyncpg://")

    def test_contains_host(self):
        s = self._make(host="rds.example.com")
        assert "rds.example.com" in s.database_url

    def test_contains_port(self):
        s = self._make(port=5433)
        assert ":5433/" in s.database_url

    def test_contains_dbname(self):
        s = self._make(name="tododb")
        assert "/tododb" in s.database_url

    def test_contains_user(self):
        s = self._make(user="todoapp")
        assert "todoapp:" in s.database_url

    def test_url_format(self):
        s = self._make(host="h", port=5432, name="db", user="u", password="p")
        assert s.database_url == "postgresql+asyncpg://u:p@h:5432/db"


# ─── DATABASE_URL_SYNC property ───────────────────────────────────────────────

class TestDatabaseURLSync:
    def _make(self, host="h", port=5432, name="db",
              user="u", password="p"):
        # Pass DATABASE_URL=None explicitly to bypass the env var set by conftest.
        return Settings(
            DB_HOST=host, DB_PORT=port, DB_NAME=name,
            DB_USER=user, DB_PASSWORD=password,
            DATABASE_URL=None,
        )

    def test_uses_psycopg2_driver(self):
        s = self._make()
        assert s.DATABASE_URL_SYNC.startswith("postgresql+psycopg2://")

    def test_sync_url_format(self):
        s = self._make(host="h", port=5432, name="db", user="u", password="p")
        assert s.DATABASE_URL_SYNC == "postgresql+psycopg2://u:p@h:5432/db"

    def test_async_and_sync_differ_only_in_driver(self):
        s = self._make()
        async_url = s.database_url.replace("postgresql+asyncpg", "")
        sync_url = s.DATABASE_URL_SYNC.replace("postgresql+psycopg2", "")
        assert async_url == sync_url


# ─── APP_ENV toggles ─────────────────────────────────────────────────────────

class TestAppEnvSettings:
    def test_development_env(self):
        s = Settings(
            APP_ENV="development",
            DB_HOST="h", DB_PORT=5432, DB_NAME="n",
            DB_USER="u", DB_PASSWORD="p",
        )
        assert s.APP_ENV == "development"

    def test_test_env(self):
        s = Settings(
            APP_ENV="test",
            DB_HOST="h", DB_PORT=5432, DB_NAME="n",
            DB_USER="u", DB_PASSWORD="p",
        )
        assert s.APP_ENV == "test"
