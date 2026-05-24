"""Burndown + velocity (5.5)."""
import pytest


@pytest.mark.asyncio
async def test_burndown_for_empty_project(client):
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    resp = await client.get(f"/api/v1/analytics/projects/{proj.json()['id']}/burndown")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["velocity_per_week"] == 0
    assert len(body["points"]) >= 15  # default 14-day window


@pytest.mark.asyncio
async def test_burndown_drops_with_completions(client):
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    pid = proj.json()["id"]
    # Create 3 tasks; complete 2 of them.
    ids = []
    for i in range(3):
        t = await client.post(
            "/api/v1/tasks/", json={"project_id": pid, "title": f"T{i}"}
        )
        ids.append(t.json()["id"])
    for i in (0, 1):
        await client.put(f"/api/v1/tasks/{ids[i]}", json={"status": "done"})

    body = (await client.get(f"/api/v1/analytics/projects/{pid}/burndown")).json()
    assert body["total"] == 3
    # Today's point should have remaining=1, completed=2.
    last = body["points"][-1]
    assert last["remaining"] == 1
    assert last["completed"] == 2


@pytest.mark.asyncio
async def test_burndown_isolated_per_workspace(client, second_client):
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    pid = proj.json()["id"]
    # Bob can't peek at Alice's burndown.
    resp = await second_client.get(f"/api/v1/analytics/projects/{pid}/burndown")
    assert resp.status_code == 404
