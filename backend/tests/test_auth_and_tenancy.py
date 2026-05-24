"""Auth + multi-tenancy guard rails.

Covers registration, login, /me, workspace switching, and the critical
invariant that one workspace can't see another workspace's data.
"""
import pytest


# ---- auth flow ------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_returns_token_and_creates_workspace(unauthed_client):
    resp = await unauthed_client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@example.com",
            "password": "Test-Password-1!",
            "full_name": "New User",
            "workspace_name": "First WS",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["email"] == "new@example.com"
    assert body["workspace"]["name"] == "First WS"


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(unauthed_client):
    payload = {
        "email": "dup@example.com",
        "password": "Test-Password-1!",
        "full_name": "X",
    }
    first = await unauthed_client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = await unauthed_client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_login_with_valid_credentials(unauthed_client):
    await unauthed_client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "password": "Test-Password-1!",
            "full_name": "L",
        },
    )
    resp = await unauthed_client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "Test-Password-1!"},
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


@pytest.mark.asyncio
async def test_login_rejects_bad_password(unauthed_client):
    await unauthed_client.post(
        "/api/v1/auth/register",
        json={
            "email": "bad@example.com",
            "password": "Test-Password-1!",
            "full_name": "B",
        },
    )
    resp = await unauthed_client.post(
        "/api/v1/auth/login",
        json={"email": "bad@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user_and_workspaces(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "alice@example.com"
    assert body["active_workspace"]["name"] == "Test Workspace"
    assert len(body["workspaces"]) == 1


@pytest.mark.asyncio
async def test_switch_workspace(client):
    # Create a second workspace under the SAME user
    new_ws = await client.post(
        "/api/v1/workspaces/", json={"name": "Second WS"}
    )
    assert new_ws.status_code == 201
    new_ws_id = new_ws.json()["id"]

    resp = await client.post(f"/api/v1/auth/switch-workspace/{new_ws_id}")
    assert resp.status_code == 200
    assert resp.json()["workspace"]["id"] == new_ws_id


@pytest.mark.asyncio
async def test_cannot_switch_to_foreign_workspace(client, second_client):
    foreign_ws_id = second_client.auth_response["workspace"]["id"]
    resp = await client.post(f"/api/v1/auth/switch-workspace/{foreign_ws_id}")
    assert resp.status_code == 403


# ---- gating on every protected route --------------------------------------


@pytest.mark.asyncio
async def test_protected_routes_reject_anonymous(unauthed_client):
    """Every /api/v1/* non-auth route must 401 without a Bearer token."""
    for path in [
        "/api/v1/projects/",
        "/api/v1/tasks/",
        "/api/v1/milestones/",
        "/api/v1/tags/",
        "/api/v1/auth/me",
    ]:
        resp = await unauthed_client.get(path)
        assert resp.status_code == 401, f"{path} should require auth, got {resp.status_code}"


@pytest.mark.asyncio
async def test_invalid_token_is_rejected(unauthed_client):
    resp = await unauthed_client.get(
        "/api/v1/projects/", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_malformed_authorization_header(unauthed_client):
    resp = await unauthed_client.get(
        "/api/v1/projects/", headers={"Authorization": "Token abc"}
    )
    assert resp.status_code == 401


# ---- tenant isolation: A's data must be invisible to B --------------------


@pytest.mark.asyncio
async def test_other_workspace_cannot_list_my_projects(client, second_client):
    # Alice creates a project
    proj = await client.post(
        "/api/v1/projects/", json={"name": "Alice Proj", "owner": "alice"}
    )
    assert proj.status_code == 201

    # Bob's list must not contain it
    resp = await second_client.get("/api/v1/projects/")
    titles = [p["name"] for p in resp.json()["items"]]
    assert "Alice Proj" not in titles


@pytest.mark.asyncio
async def test_other_workspace_cannot_get_my_project(client, second_client):
    proj = await client.post(
        "/api/v1/projects/", json={"name": "Alice Proj", "owner": "alice"}
    )
    pid = proj.json()["id"]
    resp = await second_client.get(f"/api/v1/projects/{pid}")
    # Should 404, not 403 — never leak existence to a foreign tenant.
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_other_workspace_cannot_create_task_against_my_project(
    client, second_client
):
    proj = await client.post(
        "/api/v1/projects/", json={"name": "Alice Proj", "owner": "alice"}
    )
    pid = proj.json()["id"]
    resp = await second_client.post(
        "/api/v1/tasks/",
        json={"project_id": pid, "title": "Bob's intrusion"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_other_workspace_cannot_get_my_task(client, second_client):
    proj = await client.post(
        "/api/v1/projects/", json={"name": "P", "owner": "alice"}
    )
    pid = proj.json()["id"]
    task = await client.post(
        "/api/v1/tasks/", json={"project_id": pid, "title": "T"}
    )
    tid = task.json()["id"]
    resp = await second_client.get(f"/api/v1/tasks/{tid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_other_workspace_does_not_see_my_global_stats(client, second_client):
    proj = await client.post(
        "/api/v1/projects/", json={"name": "P", "owner": "alice"}
    )
    pid = proj.json()["id"]
    from datetime import date

    await client.post(
        "/api/v1/tasks/",
        json={"project_id": pid, "title": "Due now", "due_date": str(date.today())},
    )
    # Alice sees 1, Bob sees 0.
    a = (await client.get("/api/v1/tasks/stats/due-today")).json()
    b = (await second_client.get("/api/v1/tasks/stats/due-today")).json()
    assert len(a) == 1
    assert len(b) == 0


@pytest.mark.asyncio
async def test_other_workspace_cannot_bulk_update_my_tasks(client, second_client):
    proj = await client.post(
        "/api/v1/projects/", json={"name": "P", "owner": "alice"}
    )
    pid = proj.json()["id"]
    task = await client.post(
        "/api/v1/tasks/", json={"project_id": pid, "title": "T"}
    )
    tid = task.json()["id"]
    # Bob tries to bulk-update Alice's task.
    resp = await second_client.post(
        "/api/v1/tasks/bulk",
        json={"ids": [tid], "patch": {"status": "done"}},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_other_workspace_cannot_query_my_project_health(client, second_client):
    proj = await client.post(
        "/api/v1/projects/", json={"name": "P", "owner": "alice"}
    )
    pid = proj.json()["id"]
    resp = await second_client.get(f"/api/v1/ai/projects/{pid}/health")
    assert resp.status_code == 404
