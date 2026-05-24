import pytest


@pytest.mark.asyncio
async def test_create_subtask(client):
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    pid = proj.json()["id"]

    parent = await client.post(
        "/api/v1/tasks/",
        json={"project_id": pid, "title": "Parent"},
    )
    parent_id = parent.json()["id"]

    sub = await client.post(
        "/api/v1/tasks/",
        json={"project_id": pid, "title": "Child", "parent_task_id": parent_id},
    )
    assert sub.status_code == 201
    assert sub.json()["parent_task_id"] == parent_id

    listed = await client.get(f"/api/v1/tasks/{parent_id}/subtasks")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["title"] == "Child"


@pytest.mark.asyncio
async def test_subtask_requires_same_project(client):
    p1 = (await client.post("/api/v1/projects/", json={"name": "A", "owner": "u"})).json()
    p2 = (await client.post("/api/v1/projects/", json={"name": "B", "owner": "u"})).json()

    parent = (
        await client.post(
            "/api/v1/tasks/", json={"project_id": p1["id"], "title": "Parent"}
        )
    ).json()

    bad = await client.post(
        "/api/v1/tasks/",
        json={
            "project_id": p2["id"],
            "title": "WrongProject",
            "parent_task_id": parent["id"],
        },
    )
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_task_cannot_be_own_parent(client):
    proj = (await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})).json()
    task = (
        await client.post(
            "/api/v1/tasks/", json={"project_id": proj["id"], "title": "T"}
        )
    ).json()
    bad = await client.put(
        f"/api/v1/tasks/{task['id']}",
        json={"parent_task_id": task["id"]},
    )
    assert bad.status_code == 400
