import pytest
import uuid
from datetime import date, timedelta


@pytest.mark.asyncio
async def test_create_task(client):
    project_resp = await client.post("/api/v1/projects/", json={
        "name": "Task Project",
        "owner": "Alice",
    })
    project_id = project_resp.json()["id"]

    response = await client.post("/api/v1/tasks/", json={
        "project_id": str(project_id),
        "title": "Test Task",
        "description": "A test task",
        "status": "todo",
        "priority": "high",
        "assignee": "Bob",
        "due_date": str(date.today()),
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Task"
    assert data["project_id"] == str(project_id)


@pytest.mark.asyncio
async def test_create_task_project_not_found(client):
    response = await client.post("/api/v1/tasks/", json={
        "project_id": str(uuid.uuid4()),
        "title": "Orphan Task",
    })
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_tasks(client):
    project_resp = await client.post("/api/v1/projects/", json={
        "name": "Task Project",
        "owner": "Alice",
    })
    project_id = project_resp.json()["id"]

    await client.post("/api/v1/tasks/", json={
        "project_id": str(project_id),
        "title": "Task 1",
    })
    await client.post("/api/v1/tasks/", json={
        "project_id": str(project_id),
        "title": "Task 2",
    })

    response = await client.get("/api/v1/tasks/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_task(client):
    project_resp = await client.post("/api/v1/projects/", json={
        "name": "Task Project",
        "owner": "Alice",
    })
    project_id = project_resp.json()["id"]

    create_resp = await client.post("/api/v1/tasks/", json={
        "project_id": str(project_id),
        "title": "Detail Task",
    })
    task_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Detail Task"


@pytest.mark.asyncio
async def test_update_task(client):
    project_resp = await client.post("/api/v1/projects/", json={
        "name": "Task Project",
        "owner": "Alice",
    })
    project_id = project_resp.json()["id"]

    create_resp = await client.post("/api/v1/tasks/", json={
        "project_id": str(project_id),
        "title": "Old Title",
    })
    task_id = create_resp.json()["id"]

    response = await client.put(f"/api/v1/tasks/{task_id}", json={
        "title": "New Title",
        "status": "in_progress",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Title"
    assert data["status"] == "in_progress"


@pytest.mark.asyncio
async def test_delete_task(client):
    project_resp = await client.post("/api/v1/projects/", json={
        "name": "Task Project",
        "owner": "Alice",
    })
    project_id = project_resp.json()["id"]

    create_resp = await client.post("/api/v1/tasks/", json={
        "project_id": str(project_id),
        "title": "Delete Me",
    })
    task_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 204
    get_resp = await client.get(f"/api/v1/tasks/{task_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_tasks_due_today(client):
    project_resp = await client.post("/api/v1/projects/", json={
        "name": "Task Project",
        "owner": "Alice",
    })
    project_id = project_resp.json()["id"]

    await client.post("/api/v1/tasks/", json={
        "project_id": str(project_id),
        "title": "Due Today",
        "due_date": str(date.today()),
    })

    response = await client.get("/api/v1/tasks/stats/due-today")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Due Today"


@pytest.mark.asyncio
async def test_tasks_overdue(client):
    project_resp = await client.post("/api/v1/projects/", json={
        "name": "Task Project",
        "owner": "Alice",
    })
    project_id = project_resp.json()["id"]

    await client.post("/api/v1/tasks/", json={
        "project_id": str(project_id),
        "title": "Overdue Task",
        "due_date": str(date.today() - timedelta(days=1)),
    })

    response = await client.get("/api/v1/tasks/stats/overdue")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Overdue Task"


@pytest.mark.asyncio
async def test_completed_tasks_count(client):
    project_resp = await client.post("/api/v1/projects/", json={
        "name": "Task Project",
        "owner": "Alice",
    })
    project_id = project_resp.json()["id"]

    await client.post("/api/v1/tasks/", json={
        "project_id": str(project_id),
        "title": "Done Task",
        "status": "done",
    })

    response = await client.get("/api/v1/tasks/stats/completed-count")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
