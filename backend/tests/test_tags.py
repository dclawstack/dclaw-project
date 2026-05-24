import pytest


@pytest.mark.asyncio
async def test_create_and_list_tag(client):
    resp = await client.post("/api/v1/tags/", json={"name": "urgent", "color": "#ef4444"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "urgent"
    assert data["color"] == "#ef4444"
    assert "id" in data

    list_resp = await client.get("/api/v1/tags/")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_duplicate_tag_rejected(client):
    await client.post("/api/v1/tags/", json={"name": "design"})
    dup = await client.post("/api/v1/tags/", json={"name": "design"})
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_attach_tag_to_project_and_task(client):
    tag_resp = await client.post("/api/v1/tags/", json={"name": "backend"})
    tag_id = tag_resp.json()["id"]

    project_resp = await client.post(
        "/api/v1/projects/",
        json={"name": "Tagged Project", "owner": "Alice", "tag_ids": [tag_id]},
    )
    assert project_resp.status_code == 201
    proj = project_resp.json()
    assert len(proj["tags"]) == 1
    assert proj["tags"][0]["name"] == "backend"

    project_id = proj["id"]
    task_resp = await client.post(
        "/api/v1/tasks/",
        json={
            "project_id": project_id,
            "title": "Tagged Task",
            "tag_ids": [tag_id],
        },
    )
    assert task_resp.status_code == 201
    assert task_resp.json()["tags"][0]["name"] == "backend"


@pytest.mark.asyncio
async def test_filter_projects_by_tag(client):
    t1 = (await client.post("/api/v1/tags/", json={"name": "alpha"})).json()
    t2 = (await client.post("/api/v1/tags/", json={"name": "beta"})).json()

    await client.post(
        "/api/v1/projects/",
        json={"name": "P1", "owner": "u", "tag_ids": [t1["id"]]},
    )
    await client.post(
        "/api/v1/projects/",
        json={"name": "P2", "owner": "u", "tag_ids": [t2["id"]]},
    )

    resp = await client.get("/api/v1/projects/?tag=alpha")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "P1"
