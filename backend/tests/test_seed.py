"""Tests for the demo seed / clear endpoints."""
import pytest


@pytest.mark.asyncio
async def test_seed_creates_demo_workspace_and_returns_usable_token(unauthed_client):
    resp = await unauthed_client.post("/api/v1/seed")
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["seeded"] is True
    assert body["demo_email"] == "demo@dclaw.dev"
    assert body["projects"] >= 4
    assert body["tasks"] >= 1
    assert body["milestones"] >= 1
    token = body["access_token"]
    assert token

    # The returned token must be a working API credential.
    me = await unauthed_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200, me.text

    projects = await unauthed_client.get(
        "/api/v1/projects/", headers={"Authorization": f"Bearer {token}"}
    )
    assert projects.status_code == 200
    assert projects.json()["total"] == body["projects"]


@pytest.mark.asyncio
async def test_seed_is_idempotent(unauthed_client):
    first = await unauthed_client.post("/api/v1/seed")
    assert first.status_code == 201
    # A second seed must not blow up on the duplicate demo email/slug.
    second = await unauthed_client.post("/api/v1/seed")
    assert second.status_code == 201, second.text
    assert second.json()["projects"] == first.json()["projects"]


@pytest.mark.asyncio
async def test_clear_wipes_everything(unauthed_client):
    seeded = await unauthed_client.post("/api/v1/seed")
    token = seeded.json()["access_token"]

    cleared = await unauthed_client.delete("/api/v1/seed")
    assert cleared.status_code == 200
    assert cleared.json()["cleared"] is True

    # The demo user is gone, so its token no longer resolves to a user.
    me = await unauthed_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 401
