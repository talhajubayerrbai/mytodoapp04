"""
Unit tests for individual Todo CRUD endpoints.
"""
import pytest


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _create(client, title="Test todo", **kwargs):
    payload = {"title": title, **kwargs}
    resp = await client.post("/api/todos/", json=payload)
    assert resp.status_code == 201
    return resp.json()


# ─── Create ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_todo_minimal(client, clean_db):
    body = await _create(client, "Buy milk")
    assert body["id"] > 0
    assert body["title"] == "Buy milk"
    assert body["completed"] is False
    assert body["priority"] == "medium"
    assert body["description"] is None
    assert body["due_date"] is None


@pytest.mark.asyncio
async def test_create_todo_full(client, clean_db):
    body = await _create(
        client,
        title="Full todo",
        description="A description",
        priority="high",
        due_date="2030-01-01T00:00:00Z",
    )
    assert body["title"] == "Full todo"
    assert body["description"] == "A description"
    assert body["priority"] == "high"
    assert body["due_date"] is not None


@pytest.mark.asyncio
async def test_create_todo_empty_title_rejected(client, clean_db):
    resp = await client.post("/api/todos/", json={"title": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_todo_title_too_long_rejected(client, clean_db):
    resp = await client.post("/api/todos/", json={"title": "x" * 256})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_todo_invalid_priority_rejected(client, clean_db):
    resp = await client.post("/api/todos/", json={"title": "Bad", "priority": "ultra"})
    assert resp.status_code == 422


# ─── Get by ID ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_todo_by_id(client, clean_db):
    created = await _create(client, "Fetch me")
    resp = await client.get(f"/api/todos/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]
    assert resp.json()["title"] == "Fetch me"


@pytest.mark.asyncio
async def test_get_todo_not_found(client, clean_db):
    resp = await client.get("/api/todos/999999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ─── Update ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_todo_title(client, clean_db):
    created = await _create(client, "Old title")
    resp = await client.put(f"/api/todos/{created['id']}", json={"title": "New title"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "New title"


@pytest.mark.asyncio
async def test_update_todo_completed(client, clean_db):
    created = await _create(client, "Mark done")
    resp = await client.put(f"/api/todos/{created['id']}", json={"completed": True})
    assert resp.status_code == 200
    assert resp.json()["completed"] is True


@pytest.mark.asyncio
async def test_update_todo_priority(client, clean_db):
    created = await _create(client, "Priority change")
    resp = await client.put(f"/api/todos/{created['id']}", json={"priority": "low"})
    assert resp.status_code == 200
    assert resp.json()["priority"] == "low"


@pytest.mark.asyncio
async def test_update_todo_not_found(client, clean_db):
    resp = await client.put("/api/todos/999999", json={"title": "Ghost"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_todo_empty_title_rejected(client, clean_db):
    created = await _create(client, "Valid")
    resp = await client.put(f"/api/todos/{created['id']}", json={"title": ""})
    assert resp.status_code == 422


# ─── Delete ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_todo(client, clean_db):
    created = await _create(client, "Delete me")
    resp = await client.delete(f"/api/todos/{created['id']}")
    assert resp.status_code == 204
    # Confirm it's gone
    get_resp = await client.get(f"/api/todos/{created['id']}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_todo_not_found(client, clean_db):
    resp = await client.delete("/api/todos/999999")
    assert resp.status_code == 404


# ─── Toggle ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toggle_todo_completes(client, clean_db):
    created = await _create(client, "Toggle me")
    assert created["completed"] is False
    resp = await client.patch(f"/api/todos/{created['id']}/toggle")
    assert resp.status_code == 200
    assert resp.json()["completed"] is True


@pytest.mark.asyncio
async def test_toggle_todo_uncompletes(client, clean_db):
    created = await _create(client, "Toggle back")
    # Complete it first
    await client.patch(f"/api/todos/{created['id']}/toggle")
    # Then toggle again
    resp = await client.patch(f"/api/todos/{created['id']}/toggle")
    assert resp.status_code == 200
    assert resp.json()["completed"] is False


@pytest.mark.asyncio
async def test_toggle_todo_not_found(client, clean_db):
    resp = await client.patch("/api/todos/999999/toggle")
    assert resp.status_code == 404


# ─── Response shape ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_todo_response_has_all_fields(client, clean_db):
    created = await _create(client, "Shape test")
    required = {"id", "title", "description", "completed", "priority",
                "due_date", "created_at", "updated_at"}
    assert required.issubset(set(created.keys()))
