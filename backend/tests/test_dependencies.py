"""Task dependencies + CPM (5.8 + 6.3)."""
import pytest


async def _project_with_tasks(client, n=3):
    proj = (await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})).json()
    pid = proj["id"]
    tasks = []
    for i in range(n):
        t = await client.post(
            "/api/v1/tasks/",
            json={"project_id": pid, "title": f"T{i}", "estimated_hours": 16},
        )
        tasks.append(t.json())
    return pid, tasks


@pytest.mark.asyncio
async def test_add_and_list_dependency(client):
    _, [a, b, _c] = await _project_with_tasks(client)
    resp = await client.post(
        f"/api/v1/tasks/{b['id']}/dependencies",
        json={"depends_on_task_id": a["id"]},
    )
    assert resp.status_code == 201
    listed = await client.get(f"/api/v1/tasks/{b['id']}/dependencies")
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_dependency_blocks_cycle(client):
    _, [a, b, c] = await _project_with_tasks(client)
    await client.post(
        f"/api/v1/tasks/{b['id']}/dependencies",
        json={"depends_on_task_id": a["id"]},
    )
    await client.post(
        f"/api/v1/tasks/{c['id']}/dependencies",
        json={"depends_on_task_id": b["id"]},
    )
    # A → B → C exists. Adding A depends_on C would close the cycle.
    bad = await client.post(
        f"/api/v1/tasks/{a['id']}/dependencies",
        json={"depends_on_task_id": c["id"]},
    )
    assert bad.status_code == 409


@pytest.mark.asyncio
async def test_dependency_rejects_self(client):
    _, [a, *_] = await _project_with_tasks(client, n=1)
    resp = await client.post(
        f"/api/v1/tasks/{a['id']}/dependencies",
        json={"depends_on_task_id": a["id"]},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_dependency_rejects_cross_project(client):
    p1, [t1, *_] = await _project_with_tasks(client, n=1)
    p2, [t2, *_] = await _project_with_tasks(client, n=1)
    resp = await client.post(
        f"/api/v1/tasks/{t1['id']}/dependencies",
        json={"depends_on_task_id": t2["id"]},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_critical_path_orders_chain(client):
    pid, [a, b, c] = await _project_with_tasks(client)
    await client.post(
        f"/api/v1/tasks/{b['id']}/dependencies",
        json={"depends_on_task_id": a["id"]},
    )
    await client.post(
        f"/api/v1/tasks/{c['id']}/dependencies",
        json={"depends_on_task_id": b["id"]},
    )
    resp = await client.get(f"/api/v1/projects/{pid}/critical-path")
    assert resp.status_code == 200
    cp = resp.json()
    # 16h estimate ≈ 2 day-each; total chain length = 6 days.
    assert cp["total_duration_days"] == 6
    assert len(cp["critical_chain"]) == 3
    assert cp["critical_chain"][0] == a["id"]
    assert cp["critical_chain"][-1] == c["id"]
    # Every task on the critical chain has zero slack.
    for s in cp["schedule"]:
        if s["task_id"] in cp["critical_chain"]:
            assert s["slack"] == 0


@pytest.mark.asyncio
async def test_critical_path_handles_parallel_branches(client):
    pid, [a, b, _c] = await _project_with_tasks(client, n=3)
    # B depends on A, but C has no deps → C runs in parallel with B.
    await client.post(
        f"/api/v1/tasks/{b['id']}/dependencies",
        json={"depends_on_task_id": a["id"]},
    )
    resp = await client.get(f"/api/v1/projects/{pid}/critical-path")
    cp = resp.json()
    # Longest chain: A (2d) → B (2d) = 4d. Standalone C (2d) shorter.
    assert cp["total_duration_days"] == 4
