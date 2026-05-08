import pytest
import uuid
from datetime import date


@pytest.mark.asyncio
async def test_create_milestone(client):
    project_resp = await client.post("/api/v1/projects/", json={
        "name": "Milestone Project",
        "owner": "Alice",
    })
    project_id = project_resp.json()["id"]

    response = await client.post("/api/v1/milestones/", json={
        "project_id": str(project_id),
        "name": "Test Milestone",
        "description": "A test milestone",
        "target_date": str(date.today()),
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Milestone"
    assert data["completed"] is False


@pytest.mark.asyncio
async def test_create_milestone_project_not_found(client):
    response = await client.post("/api/v1/milestones/", json={
        "project_id": str(uuid.uuid4()),
        "name": "Orphan Milestone",
        "target_date": str(date.today()),
    })
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_milestones(client):
    project_resp = await client.post("/api/v1/projects/", json={
        "name": "Milestone Project",
        "owner": "Alice",
    })
    project_id = project_resp.json()["id"]

    await client.post("/api/v1/milestones/", json={
        "project_id": str(project_id),
        "name": "Milestone 1",
        "target_date": str(date.today()),
    })
    await client.post("/api/v1/milestones/", json={
        "project_id": str(project_id),
        "name": "Milestone 2",
        "target_date": str(date.today()),
    })

    response = await client.get("/api/v1/milestones/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_milestone(client):
    project_resp = await client.post("/api/v1/projects/", json={
        "name": "Milestone Project",
        "owner": "Alice",
    })
    project_id = project_resp.json()["id"]

    create_resp = await client.post("/api/v1/milestones/", json={
        "project_id": str(project_id),
        "name": "Detail Milestone",
        "target_date": str(date.today()),
    })
    milestone_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/milestones/{milestone_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Detail Milestone"


@pytest.mark.asyncio
async def test_update_milestone(client):
    project_resp = await client.post("/api/v1/projects/", json={
        "name": "Milestone Project",
        "owner": "Alice",
    })
    project_id = project_resp.json()["id"]

    create_resp = await client.post("/api/v1/milestones/", json={
        "project_id": str(project_id),
        "name": "Old Name",
        "target_date": str(date.today()),
    })
    milestone_id = create_resp.json()["id"]

    response = await client.put(f"/api/v1/milestones/{milestone_id}", json={
        "name": "New Name",
        "completed": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["completed"] is True


@pytest.mark.asyncio
async def test_delete_milestone(client):
    project_resp = await client.post("/api/v1/projects/", json={
        "name": "Milestone Project",
        "owner": "Alice",
    })
    project_id = project_resp.json()["id"]

    create_resp = await client.post("/api/v1/milestones/", json={
        "project_id": str(project_id),
        "name": "Delete Me",
        "target_date": str(date.today()),
    })
    milestone_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/milestones/{milestone_id}")
    assert response.status_code == 204
    get_resp = await client.get(f"/api/v1/milestones/{milestone_id}")
    assert get_resp.status_code == 404
