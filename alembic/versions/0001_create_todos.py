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
    # Create the priority enum type first
    priority_enum = sa.Enum("low", "medium", "high", name="priority_enum")
    priority_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "todos",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "priority",
            sa.Enum("low", "medium", "high", name="priority_enum"),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_todos_id"), "todos", ["id"], unique=False)
    op.create_index(op.f("ix_todos_title"), "todos", ["title"], unique=False)
    op.create_index(op.f("ix_todos_completed"), "todos", ["completed"], unique=False)
    op.create_index(op.f("ix_todos_priority"), "todos", ["priority"], unique=False)

    # Auto-update updated_at via a trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    op.execute("""
        CREATE TRIGGER todos_updated_at
        BEFORE UPDATE ON todos
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS todos_updated_at ON todos")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column")
    op.drop_index(op.f("ix_todos_priority"), table_name="todos")
    op.drop_index(op.f("ix_todos_completed"), table_name="todos")
    op.drop_index(op.f("ix_todos_title"), table_name="todos")
    op.drop_index(op.f("ix_todos_id"), table_name="todos")
    op.drop_table("todos")
    sa.Enum(name="priority_enum").drop(op.get_bind(), checkfirst=True)
