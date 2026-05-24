import pytest


async def _make_task(client) -> str:
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    task = await client.post(
        "/api/v1/tasks/",
        json={"project_id": proj.json()["id"], "title": "T"},
    )
    return task.json()["id"]


@pytest.mark.asyncio
async def test_create_and_list_comments(client):
    task_id = await _make_task(client)
    c1 = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"author": "alice", "body": "first"},
    )
    assert c1.status_code == 201
    c2 = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"author": "bob", "body": "second"},
    )
    assert c2.status_code == 201

    listed = await client.get(f"/api/v1/tasks/{task_id}/comments")
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 2
    assert items[0]["body"] == "first"
    assert items[1]["body"] == "second"


@pytest.mark.asyncio
async def test_comment_on_missing_task(client):
    import uuid

    resp = await client.post(
        f"/api/v1/tasks/{uuid.uuid4()}/comments",
        json={"author": "x", "body": "y"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_and_delete_comment(client):
    task_id = await _make_task(client)
    c = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"author": "alice", "body": "orig"},
    )
    cid = c.json()["id"]

    up = await client.put(f"/api/v1/tasks/comments/{cid}", json={"body": "edited"})
    assert up.status_code == 200
    assert up.json()["body"] == "edited"

    rm = await client.delete(f"/api/v1/tasks/comments/{cid}")
    assert rm.status_code == 204

    listed = await client.get(f"/api/v1/tasks/{task_id}/comments")
    assert len(listed.json()) == 0
