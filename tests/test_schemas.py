"""
Pure unit tests for Pydantic schema validation — no database or HTTP needed.
"""
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.schemas import TodoCreate, TodoUpdate, BulkDeleteRequest, BulkCompleteRequest
from app.models import Priority


# ─── TodoCreate ───────────────────────────────────────────────────────────────

class TestTodoCreate:
    def test_minimal_valid(self):
        t = TodoCreate(title="Hello")
        assert t.title == "Hello"
        assert t.priority == Priority.medium
        assert t.description is None
        assert t.due_date is None

    def test_full_valid(self):
        t = TodoCreate(
            title="Full",
            description="Desc",
            priority="high",
            due_date="2030-06-01T00:00:00Z",
        )
        assert t.priority == Priority.high
        assert isinstance(t.due_date, datetime)

    def test_empty_title_raises(self):
        with pytest.raises(ValidationError):
            TodoCreate(title="")

    def test_title_too_long_raises(self):
        with pytest.raises(ValidationError):
            TodoCreate(title="x" * 256)

    def test_description_too_long_raises(self):
        with pytest.raises(ValidationError):
            TodoCreate(title="Ok", description="d" * 2001)

    def test_invalid_priority_raises(self):
        with pytest.raises(ValidationError):
            TodoCreate(title="T", priority="ultra")

    def test_priority_enum_values(self):
        for p in ("low", "medium", "high"):
            t = TodoCreate(title="T", priority=p)
            assert t.priority == p

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError):
            TodoCreate()

    def test_title_max_boundary(self):
        t = TodoCreate(title="x" * 255)
        assert len(t.title) == 255

    def test_title_min_boundary(self):
        t = TodoCreate(title="x")
        assert t.title == "x"


# ─── TodoUpdate ───────────────────────────────────────────────────────────────

class TestTodoUpdate:
    def test_empty_update_is_valid(self):
        u = TodoUpdate()
        assert u.title is None
        assert u.completed is None
        assert u.priority is None

    def test_partial_title_update(self):
        u = TodoUpdate(title="New title")
        assert u.title == "New title"

    def test_empty_title_raises(self):
        with pytest.raises(ValidationError):
            TodoUpdate(title="")

    def test_completed_bool(self):
        u = TodoUpdate(completed=True)
        assert u.completed is True
        u2 = TodoUpdate(completed=False)
        assert u2.completed is False

    def test_invalid_priority_raises(self):
        with pytest.raises(ValidationError):
            TodoUpdate(priority="super")

    def test_valid_priority_update(self):
        u = TodoUpdate(priority="low")
        assert u.priority == Priority.low

    def test_due_date_update(self):
        u = TodoUpdate(due_date="2025-12-31T00:00:00Z")
        assert isinstance(u.due_date, datetime)


# ─── BulkDeleteRequest ────────────────────────────────────────────────────────

class TestBulkDeleteRequest:
    def test_valid(self):
        req = BulkDeleteRequest(ids=[1, 2, 3])
        assert req.ids == [1, 2, 3]

    def test_empty_ids_raises(self):
        with pytest.raises(ValidationError):
            BulkDeleteRequest(ids=[])

    def test_single_id(self):
        req = BulkDeleteRequest(ids=[42])
        assert 42 in req.ids


# ─── BulkCompleteRequest ──────────────────────────────────────────────────────

class TestBulkCompleteRequest:
    def test_defaults_completed_true(self):
        req = BulkCompleteRequest(ids=[1])
        assert req.completed is True

    def test_explicit_false(self):
        req = BulkCompleteRequest(ids=[1, 2], completed=False)
        assert req.completed is False

    def test_empty_ids_raises(self):
        with pytest.raises(ValidationError):
            BulkCompleteRequest(ids=[])
