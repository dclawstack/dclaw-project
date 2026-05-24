import pytest
from datetime import date, timedelta


async def _make_project(client, **kwargs):
    payload = {"name": "AI Project", "owner": "alice", **kwargs}
    resp = await client.post("/api/v1/projects/", json=payload)
    return resp.json()


@pytest.mark.asyncio
async def test_copilot_chat_returns_provider(client):
    resp = await client.post(
        "/api/v1/ai/copilot/chat",
        json={"messages": [{"role": "user", "content": "Help me plan a launch"}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    # No LLM configured → heuristic provider, but the API contract is intact.
    assert data["provider"] in ("heuristic", "openrouter", "ollama")
    assert isinstance(data["text"], str)
    assert len(data["text"]) > 0


@pytest.mark.asyncio
async def test_copilot_chat_with_project_context(client):
    project = await _make_project(client)
    resp = await client.post(
        "/api/v1/ai/copilot/chat",
        json={
            "project_id": project["id"],
            "messages": [{"role": "user", "content": "What are the risks?"}],
        },
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_copilot_chat_invalid_project(client):
    import uuid

    resp = await client.post(
        "/api/v1/ai/copilot/chat",
        json={
            "project_id": str(uuid.uuid4()),
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_project_health_perfect_when_empty(client):
    project = await _make_project(client)
    resp = await client.get(f"/api/v1/ai/projects/{project['id']}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] >= 75  # green when nothing is overdue
    assert data["status"] in ("green", "yellow", "red")
    assert isinstance(data["signals"], list)
    assert len(data["signals"]) == 5


@pytest.mark.asyncio
async def test_project_health_degrades_with_overdue(client):
    project = await _make_project(client)
    pid = project["id"]
    yesterday = (date.today() - timedelta(days=2)).isoformat()
    # Add several overdue, unassigned, urgent tasks.
    for i in range(5):
        await client.post(
            "/api/v1/tasks/",
            json={
                "project_id": pid,
                "title": f"Overdue {i}",
                "due_date": yesterday,
                "priority": "urgent",
            },
        )
    resp = await client.get(f"/api/v1/ai/projects/{pid}/health")
    data = resp.json()
    assert data["score"] < 75
    assert data["status"] in ("yellow", "red")
    assert any("overdue" in r.lower() for r in data["top_risks"])


@pytest.mark.asyncio
async def test_generate_wbs_creates_new_project(client):
    resp = await client.post(
        "/api/v1/ai/generate-wbs",
        json={
            "goal": "Build a mobile time tracker",
            "deadline_days": 21,
            "team_size": 2,
            "project_name": "Tracker",
            "owner": "alice",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tasks"]) > 0
    assert len(data["milestones"]) > 0
    assert len(data["created_task_ids"]) == len(data["tasks"])
    assert len(data["created_milestone_ids"]) == len(data["milestones"])

    # Verify they persisted under the new project.
    proj_resp = await client.get(f"/api/v1/projects/{data['project_id']}")
    proj = proj_resp.json()
    assert len(proj["tasks"]) == len(data["tasks"])
    assert len(proj["milestones"]) == len(data["milestones"])


@pytest.mark.asyncio
async def test_generate_wbs_requires_name_or_existing_project(client):
    resp = await client.post(
        "/api/v1/ai/generate-wbs",
        json={"goal": "Build something", "deadline_days": 10},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_generate_wbs_into_existing_project(client):
    project = await _make_project(client, name="Existing")
    resp = await client.post(
        "/api/v1/ai/generate-wbs",
        json={
            "goal": "Onboard 100 customers in 30 days",
            "deadline_days": 30,
            "team_size": 4,
            "project_id": project["id"],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["project_id"] == project["id"]
