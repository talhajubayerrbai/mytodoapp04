"""
Unit tests for list / filter / search / sort / pagination endpoints.
"""
import pytest


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _create(client, title, **kwargs):
    payload = {"title": title, **kwargs}
    resp = await client.post("/api/todos/", json=payload)
    assert resp.status_code == 201
    return resp.json()


async def _list(client, **params):
    resp = await client.get("/api/todos/", params=params)
    assert resp.status_code == 200
    return resp.json()


# ─── List response shape ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_response_shape(client, clean_db):
    body = await _list(client)
    for key in ("items", "total", "page", "page_size", "pages"):
        assert key in body


@pytest.mark.asyncio
async def test_list_empty(client, clean_db):
    body = await _list(client)
    assert body["items"] == []
    assert body["total"] == 0


# ─── Basic listing ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_returns_created_todos(client, clean_db):
    await _create(client, "Alpha")
    await _create(client, "Beta")
    body = await _list(client)
    assert body["total"] == 2
    titles = [t["title"] for t in body["items"]]
    assert "Alpha" in titles
    assert "Beta" in titles


# ─── Filter by completed ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_filter_completed_false(client, clean_db):
    todo = await _create(client, "Active task")
    done = await _create(client, "Done task")
    await client.put(f"/api/todos/{done['id']}", json={"completed": True})

    body = await _list(client, completed="false")
    titles = [t["title"] for t in body["items"]]
    assert "Active task" in titles
    assert "Done task" not in titles


@pytest.mark.asyncio
async def test_filter_completed_true(client, clean_db):
    todo = await _create(client, "Active task 2")
    done = await _create(client, "Done task 2")
    await client.put(f"/api/todos/{done['id']}", json={"completed": True})

    body = await _list(client, completed="true")
    titles = [t["title"] for t in body["items"]]
    assert "Done task 2" in titles
    assert "Active task 2" not in titles


# ─── Filter by priority ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_filter_priority_high(client, clean_db):
    await _create(client, "High priority", priority="high")
    await _create(client, "Low priority", priority="low")

    body = await _list(client, priority="high")
    for item in body["items"]:
        assert item["priority"] == "high"


@pytest.mark.asyncio
async def test_filter_priority_low(client, clean_db):
    await _create(client, "Med task", priority="medium")
    await _create(client, "Low task", priority="low")

    body = await _list(client, priority="low")
    assert all(i["priority"] == "low" for i in body["items"])


# ─── Search ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_finds_match(client, clean_db):
    await _create(client, "Buy groceries")
    await _create(client, "Call dentist")

    body = await _list(client, search="groceries")
    titles = [t["title"] for t in body["items"]]
    assert "Buy groceries" in titles
    assert "Call dentist" not in titles


@pytest.mark.asyncio
async def test_search_case_insensitive(client, clean_db):
    await _create(client, "Read a book")

    body = await _list(client, search="READ")
    titles = [t["title"] for t in body["items"]]
    assert "Read a book" in titles


@pytest.mark.asyncio
async def test_search_no_match_returns_empty(client, clean_db):
    await _create(client, "Something here")

    body = await _list(client, search="xyznonexistent")
    assert body["total"] == 0
    assert body["items"] == []


@pytest.mark.asyncio
async def test_search_partial_match(client, clean_db):
    await _create(client, "Walk the dog")
    await _create(client, "Feed the dog")
    await _create(client, "Clean the house")

    body = await _list(client, search="dog")
    assert body["total"] == 2


# ─── Sort ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sort_by_title_asc(client, clean_db):
    await _create(client, "Zebra")
    await _create(client, "Apple")
    await _create(client, "Mango")

    body = await _list(client, sort_by="title", order="asc")
    titles = [t["title"] for t in body["items"]]
    assert titles == sorted(titles)


@pytest.mark.asyncio
async def test_sort_by_title_desc(client, clean_db):
    await _create(client, "Zebra2")
    await _create(client, "Apple2")

    body = await _list(client, sort_by="title", order="desc")
    titles = [t["title"] for t in body["items"]]
    assert titles == sorted(titles, reverse=True)


@pytest.mark.asyncio
async def test_invalid_sort_field_rejected(client, clean_db):
    resp = await client.get("/api/todos/", params={"sort_by": "nonexistent"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_order_rejected(client, clean_db):
    resp = await client.get("/api/todos/", params={"order": "random"})
    assert resp.status_code == 422


# ─── Pagination ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pagination_page_size(client, clean_db):
    for i in range(5):
        await _create(client, f"Page item {i}")

    body = await _list(client, page=1, page_size=2)
    assert len(body["items"]) == 2
    assert body["page_size"] == 2
    assert body["total"] == 5
    assert body["pages"] == 3


@pytest.mark.asyncio
async def test_pagination_second_page(client, clean_db):
    for i in range(4):
        await _create(client, f"Paged {i}")

    page1 = await _list(client, page=1, page_size=2, sort_by="title", order="asc")
    page2 = await _list(client, page=2, page_size=2, sort_by="title", order="asc")

    ids_p1 = {t["id"] for t in page1["items"]}
    ids_p2 = {t["id"] for t in page2["items"]}
    assert ids_p1.isdisjoint(ids_p2), "Pages must not overlap"


@pytest.mark.asyncio
async def test_pagination_page_out_of_range_returns_empty(client, clean_db):
    await _create(client, "Only one")

    body = await _list(client, page=999, page_size=10)
    assert body["items"] == []


@pytest.mark.asyncio
async def test_pagination_invalid_page_rejected(client, clean_db):
    resp = await client.get("/api/todos/", params={"page": 0})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_pagination_invalid_page_size_rejected(client, clean_db):
    resp = await client.get("/api/todos/", params={"page_size": 0})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_pagination_max_page_size_enforced(client, clean_db):
    resp = await client.get("/api/todos/", params={"page_size": 9999})
    assert resp.status_code == 422
