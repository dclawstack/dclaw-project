import pytest


@pytest.mark.asyncio
async def test_bulk_update_status(client):
    proj = (
        await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    ).json()
    pid = proj["id"]

    ids = []
    for i in range(3):
        t = await client.post(
            "/api/v1/tasks/",
            json={"project_id": pid, "title": f"T{i}"},
        )
        ids.append(t.json()["id"])

    bulk = await client.post(
        "/api/v1/tasks/bulk",
        json={"ids": ids, "patch": {"status": "done"}},
    )
    assert bulk.status_code == 200
    updated = bulk.json()
    assert len(updated) == 3
    for t in updated:
        assert t["status"] == "done"
        assert t["completed_at"] is not None


@pytest.mark.asyncio
async def test_search_tasks_by_query(client):
    proj = (
        await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    ).json()
    pid = proj["id"]
    for title in ["Build login UI", "Build signup UI", "Configure CI pipeline"]:
        await client.post("/api/v1/tasks/", json={"project_id": pid, "title": title})

    resp = await client.get("/api/v1/tasks/?q=signup")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Build signup UI"


@pytest.mark.asyncio
async def test_pagination(client):
    proj = (
        await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    ).json()
    pid = proj["id"]
    for i in range(5):
        await client.post("/api/v1/tasks/", json={"project_id": pid, "title": f"T{i}"})

    page1 = await client.get("/api/v1/tasks/?limit=2&offset=0")
    page2 = await client.get("/api/v1/tasks/?limit=2&offset=2")
    page3 = await client.get("/api/v1/tasks/?limit=2&offset=4")

    assert page1.json()["total"] == 5
    assert len(page1.json()["items"]) == 2
    assert len(page2.json()["items"]) == 2
    assert len(page3.json()["items"]) == 1


@pytest.mark.asyncio
async def test_project_stats(client):
    proj = (
        await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    ).json()
    pid = proj["id"]
    for status in ["todo", "in_progress", "done", "done"]:
        await client.post(
            "/api/v1/tasks/",
            json={"project_id": pid, "title": "T", "status": status},
        )

    stats = await client.get(f"/api/v1/projects/{pid}/stats")
    assert stats.status_code == 200
    data = stats.json()
    assert data["total_tasks"] == 4
    assert data["by_status"]["done"] == 2
    assert data["by_status"]["todo"] == 1
    assert data["by_status"]["in_progress"] == 1
    assert data["completion_pct"] == 50.0
