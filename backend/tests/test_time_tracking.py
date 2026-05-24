"""Time tracking (5.6)."""
import asyncio
import pytest
from datetime import datetime, timezone, timedelta


async def _task(client):
    p = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    t = await client.post("/api/v1/tasks/", json={"project_id": p.json()["id"], "title": "T"})
    return t.json()


@pytest.mark.asyncio
async def test_start_and_stop_timer(client):
    task = await _task(client)
    started = await client.post("/api/v1/time-entries/start", json={"task_id": task["id"]})
    assert started.status_code == 201
    body = started.json()
    assert body["ended_at"] is None
    # Tiny sleep so duration is non-zero.
    await asyncio.sleep(0.05)
    stopped = await client.post("/api/v1/time-entries/stop")
    assert stopped.status_code == 200
    assert stopped.json()["duration_seconds"] is not None
    assert stopped.json()["ended_at"] is not None


@pytest.mark.asyncio
async def test_starting_second_timer_stops_first(client):
    task1 = await _task(client)
    task2 = await _task(client)
    a = await client.post("/api/v1/time-entries/start", json={"task_id": task1["id"]})
    b = await client.post("/api/v1/time-entries/start", json={"task_id": task2["id"]})
    assert a.status_code == 201 and b.status_code == 201

    summary = await client.get(f"/api/v1/time-entries/task/{task1['id']}/summary")
    assert summary.json()["entries"] == 1  # the first one closed


@pytest.mark.asyncio
async def test_manual_time_entry(client):
    task = await _task(client)
    now = datetime.now(timezone.utc)
    earlier = now - timedelta(hours=2)
    resp = await client.post(
        "/api/v1/time-entries/manual",
        json={
            "task_id": task["id"],
            "started_at": earlier.isoformat(),
            "ended_at": now.isoformat(),
            "notes": "Wrote docs",
        },
    )
    assert resp.status_code == 201
    # 2h = 7200s, allow some slack for clock granularity.
    assert 7100 < resp.json()["duration_seconds"] < 7300


@pytest.mark.asyncio
async def test_manual_entry_rejects_inverted_window(client):
    task = await _task(client)
    now = datetime.now(timezone.utc)
    resp = await client.post(
        "/api/v1/time-entries/manual",
        json={
            "task_id": task["id"],
            "started_at": now.isoformat(),
            "ended_at": (now - timedelta(hours=1)).isoformat(),
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_no_active_timer_returns_null(client):
    resp = await client.get("/api/v1/time-entries/active")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_stop_without_active_timer_404s(client):
    resp = await client.post("/api/v1/time-entries/stop")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_time_entry_cross_workspace_isolation(client, second_client):
    task = await _task(client)
    bad = await second_client.post(
        "/api/v1/time-entries/start", json={"task_id": task["id"]}
    )
    assert bad.status_code == 404
