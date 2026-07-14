"""
Unit tests for health and API info endpoints.
"""
import pytest


@pytest.mark.asyncio
async def test_health_ok(client):
    resp = await client.get("/health/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "uptime" in body
    assert "database" in body


@pytest.mark.asyncio
async def test_health_db_field_present(client):
    resp = await client.get("/health/")
    body = resp.json()
    # DB status can be "ok" or an error string; either way the key must exist.
    assert "database" in body


@pytest.mark.asyncio
async def test_api_info(client):
    resp = await client.get("/api/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["app"] == "fastapi"
    assert "version" in body
    assert "db" in body
    assert "env" in body


@pytest.mark.asyncio
async def test_root_returns_html(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
