import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready(client):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_request_id_echoed(client):
    response = await client.get("/health/", headers={"x-request-id": "test-req-123"})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == "test-req-123"
