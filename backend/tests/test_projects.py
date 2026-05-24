import pytest
import uuid


@pytest.mark.asyncio
async def test_create_project(client):
    response = await client.post("/api/v1/projects/", json={
        "name": "Test Project",
        "description": "A test project",
        "status": "planning",
        "owner": "Alice",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["owner"] == "Alice"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_projects(client):
    await client.post("/api/v1/projects/", json={
        "name": "Project 1",
        "owner": "Alice",
    })
    await client.post("/api/v1/projects/", json={
        "name": "Project 2",
        "owner": "Bob",
    })
    response = await client.get("/api/v1/projects/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_project(client):
    create_resp = await client.post("/api/v1/projects/", json={
        "name": "Detail Project",
        "owner": "Alice",
    })
    project_id = create_resp.json()["id"]
    response = await client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Detail Project"
    assert "tasks" in data
    assert "milestones" in data


@pytest.mark.asyncio
async def test_get_project_not_found(client):
    response = await client.get(f"/api/v1/projects/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_project(client):
    create_resp = await client.post("/api/v1/projects/", json={
        "name": "Old Name",
        "owner": "Alice",
    })
    project_id = create_resp.json()["id"]
    response = await client.put(f"/api/v1/projects/{project_id}", json={
        "name": "New Name",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_project(client):
    create_resp = await client.post("/api/v1/projects/", json={
        "name": "Delete Me",
        "owner": "Alice",
    })
    project_id = create_resp.json()["id"]
    response = await client.delete(f"/api/v1/projects/{project_id}")
    assert response.status_code == 204
    get_resp = await client.get(f"/api/v1/projects/{project_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_project_tasks_and_milestones_routes(client):
    create_resp = await client.post("/api/v1/projects/", json={
        "name": "Project With Stuff",
        "owner": "Alice",
    })
    project_id = create_resp.json()["id"]

    tasks_resp = await client.get(f"/api/v1/projects/{project_id}/tasks")
    assert tasks_resp.status_code == 200
    assert tasks_resp.json() == []

    milestones_resp = await client.get(f"/api/v1/projects/{project_id}/milestones")
    assert milestones_resp.status_code == 200
    assert milestones_resp.json() == []
