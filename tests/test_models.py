"""
Pure unit tests for the SQLAlchemy Todo model and Priority enum.
No database connection required — tests inspect class-level attributes only.
"""
import pytest
from datetime import datetime, timezone

from app.models import Todo, Priority


# ─── Priority enum ────────────────────────────────────────────────────────────

class TestPriorityEnum:
    def test_values_exist(self):
        assert Priority.low == "low"
        assert Priority.medium == "medium"
        assert Priority.high == "high"

    def test_is_str_subclass(self):
        assert isinstance(Priority.low, str)
        assert isinstance(Priority.medium, str)
        assert isinstance(Priority.high, str)

    def test_enum_members(self):
        members = {p.value for p in Priority}
        assert members == {"low", "medium", "high"}

    def test_from_string(self):
        assert Priority("low") is Priority.low
        assert Priority("medium") is Priority.medium
        assert Priority("high") is Priority.high

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            Priority("ultra")


# ─── Todo model ───────────────────────────────────────────────────────────────

class TestTodoModel:
    def test_tablename(self):
        assert Todo.__tablename__ == "todos"

    def test_repr_contains_id_and_title(self):
        todo = Todo.__new__(Todo)
        todo.id = 7
        todo.title = "Write tests"
        todo.completed = False
        assert "7" in repr(todo)
        assert "Write tests" in repr(todo)
        assert "False" in repr(todo)

    def test_repr_format(self):
        todo = Todo.__new__(Todo)
        todo.id = 1
        todo.title = "Hello"
        todo.completed = True
        r = repr(todo)
        assert r.startswith("<Todo")
        assert "id=1" in r
        assert "completed=True" in r

    def test_columns_present(self):
        col_names = {c.key for c in Todo.__table__.columns}
        expected = {"id", "title", "description", "completed",
                    "priority", "due_date", "created_at", "updated_at"}
        assert expected.issubset(col_names)

    def test_id_is_primary_key(self):
        pk_cols = {c.key for c in Todo.__table__.primary_key}
        assert "id" in pk_cols

    def test_title_max_length(self):
        title_col = Todo.__table__.c["title"]
        assert title_col.type.length == 255

    def test_completed_default_false(self):
        completed_col = Todo.__table__.c["completed"]
        assert completed_col.default.arg is False

    def test_priority_default_medium(self):
        priority_col = Todo.__table__.c["priority"]
        assert priority_col.default.arg == Priority.medium

    def test_description_nullable(self):
        desc_col = Todo.__table__.c["description"]
        assert desc_col.nullable is True

    def test_due_date_nullable(self):
        due_col = Todo.__table__.c["due_date"]
        assert due_col.nullable is True

    def test_completed_not_nullable(self):
        completed_col = Todo.__table__.c["completed"]
        assert completed_col.nullable is False

    def test_title_not_nullable(self):
        title_col = Todo.__table__.c["title"]
        assert title_col.nullable is False
