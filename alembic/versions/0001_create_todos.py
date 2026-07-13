"""Create todos table

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. Create the enum type — fully idempotent ────────────────────────────
    # Use DO $$ … EXCEPTION to silently swallow duplicate_object errors so that
    # re-runs (e.g. after a failed first attempt) never raise DuplicateObject.
    bind.execute(sa.text(
        "DO $$ BEGIN "
        "  CREATE TYPE priority_enum AS ENUM ('low', 'medium', 'high'); "
        "EXCEPTION WHEN duplicate_object THEN null; "
        "END $$;"
    ))

    # ── 2. Create the table — fully idempotent via raw SQL ───────────────────
    # We deliberately avoid op.create_table() with sa.Enum here because some
    # SQLAlchemy / psycopg2 version combinations emit a bare CREATE TYPE even
    # when create_type=False is set on a string-based Enum column, causing a
    # DuplicateObject error on re-runs.  Using CREATE TABLE IF NOT EXISTS with
    # a raw cast is 100 % reliable regardless of driver version.
    bind.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS todos (
            id          BIGSERIAL PRIMARY KEY,
            title       VARCHAR(255)               NOT NULL,
            description TEXT,
            completed   BOOLEAN                    NOT NULL DEFAULT FALSE,
            priority    priority_enum              NOT NULL DEFAULT 'medium',
            due_date    TIMESTAMPTZ,
            created_at  TIMESTAMPTZ                NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ                NOT NULL DEFAULT NOW()
        );
    """))

    # ── 3. Indexes — each guarded so re-runs are safe ────────────────────────
    bind.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_todos_id        ON todos (id);"
    ))
    bind.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_todos_id_unique ON todos (id);"
    ))
    bind.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_todos_title     ON todos (title);"
    ))
    bind.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_todos_completed ON todos (completed);"
    ))
    bind.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_todos_priority  ON todos (priority);"
    ))

    # ── 4. Auto-update updated_at trigger — both statements are idempotent ───
    bind.execute(sa.text("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE 'plpgsql';
    """))

    bind.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'todos_updated_at'
            ) THEN
                CREATE TRIGGER todos_updated_at
                BEFORE UPDATE ON todos
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
            END IF;
        END $$;
    """))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP TRIGGER IF EXISTS todos_updated_at ON todos"))
    bind.execute(sa.text("DROP FUNCTION IF EXISTS update_updated_at_column()"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_todos_priority"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_todos_completed"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_todos_title"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_todos_id_unique"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_todos_id"))
    bind.execute(sa.text("DROP TABLE IF EXISTS todos"))
    bind.execute(sa.text("DROP TYPE IF EXISTS priority_enum"))
