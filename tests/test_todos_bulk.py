"""
Unit tests for bulk delete and bulk complete endpoints.
"""
import pytest


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _create(client, title, **kwargs):
    resp = await client.post("/api/todos/", json={"title": title, **kwargs})
    assert resp.status_code == 201
    return resp.json()


# ─── Bulk delete ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_delete_removes_todos(client, clean_db):
    t1 = await _create(client, "Bulk del 1")
    t2 = await _create(client, "Bulk del 2")
    t3 = await _create(client, "Keep me")

    resp = await client.request(
        "DELETE",
        "/api/todos/bulk/delete",
        json={"ids": [t1["id"], t2["id"]]},
    )
    assert resp.status_code == 204

    # t1 and t2 must be gone
    assert (await client.get(f"/api/todos/{t1['id']}")).status_code == 404
    assert (await client.get(f"/api/todos/{t2['id']}")).status_code == 404

    # t3 must survive
    assert (await client.get(f"/api/todos/{t3['id']}")).status_code == 200


@pytest.mark.asyncio
async def test_bulk_delete_nonexistent_ids_is_idempotent(client, clean_db):
    """Deleting IDs that don't exist should not raise an error."""
    resp = await client.request(
        "DELETE",
        "/api/todos/bulk/delete",
        json={"ids": [999991, 999992]},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_bulk_delete_empty_ids_rejected(client, clean_db):
    resp = await client.request(
        "DELETE",
        "/api/todos/bulk/delete",
        json={"ids": []},
    )
    assert resp.status_code == 422


# ─── Bulk complete ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_complete_marks_todos_done(client, clean_db):
    t1 = await _create(client, "Bulk comp 1")
    t2 = await _create(client, "Bulk comp 2")

    resp = await client.patch(
        "/api/todos/bulk/complete",
        json={"ids": [t1["id"], t2["id"]], "completed": True},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert len(result) == 2
    for item in result:
        assert item["completed"] is True


@pytest.mark.asyncio
async def test_bulk_complete_marks_todos_incomplete(client, clean_db):
    t1 = await _create(client, "Undo comp 1")
    # Complete first
    await client.patch(
        "/api/todos/bulk/complete",
        json={"ids": [t1["id"]], "completed": True},
    )
    # Now undo
    resp = await client.patch(
        "/api/todos/bulk/complete",
        json={"ids": [t1["id"]], "completed": False},
    )
    assert resp.status_code == 200
    assert resp.json()[0]["completed"] is False


@pytest.mark.asyncio
async def test_bulk_complete_returns_updated_items(client, clean_db):
    t1 = await _create(client, "Return check 1")
    t2 = await _create(client, "Return check 2")

    resp = await client.patch(
        "/api/todos/bulk/complete",
        json={"ids": [t1["id"], t2["id"]], "completed": True},
    )
    body = resp.json()
    ids_returned = {item["id"] for item in body}
    assert t1["id"] in ids_returned
    assert t2["id"] in ids_returned


@pytest.mark.asyncio
async def test_bulk_complete_empty_ids_rejected(client, clean_db):
    resp = await client.patch(
        "/api/todos/bulk/complete",
        json={"ids": [], "completed": True},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_complete_default_completed_is_true(client, clean_db):
    """completed defaults to True when not specified."""
    t1 = await _create(client, "Default complete")
    resp = await client.patch(
        "/api/todos/bulk/complete",
        json={"ids": [t1["id"]]},
    )
    assert resp.status_code == 200
    assert resp.json()[0]["completed"] is True
