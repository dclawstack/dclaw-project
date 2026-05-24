"""C2 feature coverage: agent, RAG, risk model, leveling, integrations,
documents, sprints."""
import io
import pytest
from datetime import date, timedelta

from app.services.integrations import reset_integrations


@pytest.fixture(autouse=True)
def _fresh_integrations():
    reset_integrations()
    yield
    reset_integrations()


# ---- 6.1 Agent ------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_plan_returns_full_trace(client):
    resp = await client.post(
        "/api/v1/ai/agent/plan",
        json={"goal": "Ship a mobile auth flow in 2 weeks", "max_steps": 6},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Each of the 6 steps must be present in order.
    assert [s["name"] for s in body["steps"]] == [
        "research", "wbs", "estimate", "critical_path", "assignment", "review",
    ]
    # final_output rolls them up
    assert "tasks" in body["final_output"]
    assert "review" in body["final_output"]
    assert body["status"] == "succeeded"


@pytest.mark.asyncio
async def test_agent_runs_are_listed(client):
    await client.post("/api/v1/ai/agent/plan", json={"goal": "Ship", "max_steps": 2})
    await client.post("/api/v1/ai/agent/plan", json={"goal": "Hire", "max_steps": 2})
    runs = (await client.get("/api/v1/ai/agent/runs")).json()
    assert len(runs) == 2


@pytest.mark.asyncio
async def test_agent_runs_isolated_per_workspace(client, second_client):
    await client.post("/api/v1/ai/agent/plan", json={"goal": "Ship something", "max_steps": 2})
    a = (await client.get("/api/v1/ai/agent/runs")).json()
    b = (await second_client.get("/api/v1/ai/agent/runs")).json()
    assert len(a) == 1
    assert len(b) == 0


# ---- 6.2 RAG --------------------------------------------------------------


async def _seed_content(client):
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    pid = proj.json()["id"]
    await client.post(
        "/api/v1/tasks/",
        json={
            "project_id": pid,
            "title": "Authentication flow review",
            "description": "Refactor login, signup, and password reset.",
        },
    )
    await client.post(
        "/api/v1/tasks/",
        json={
            "project_id": pid,
            "title": "Database migration cleanup",
            "description": "Squash old alembic revisions.",
        },
    )
    return pid


@pytest.mark.asyncio
async def test_rag_reindex_and_search(client):
    await _seed_content(client)
    reindex = await client.post("/api/v1/ai/reindex")
    assert reindex.status_code == 200
    assert reindex.json()["chunks"] >= 2

    search = await client.get("/api/v1/ai/search?q=login%20signup")
    assert search.status_code == 200
    hits = search.json()["hits"]
    assert any("Authentication" in h["content"] for h in hits)


@pytest.mark.asyncio
async def test_rag_isolated_per_workspace(client, second_client):
    await _seed_content(client)
    await client.post("/api/v1/ai/reindex")
    # Bob shouldn't see any hits — he has no content of his own.
    resp = await second_client.get("/api/v1/ai/search?q=login")
    assert resp.json()["hits"] == []


@pytest.mark.asyncio
async def test_rag_ask_returns_answer_with_citations(client):
    await _seed_content(client)
    await client.post("/api/v1/ai/reindex")
    resp = await client.post(
        "/api/v1/ai/ask", json={"question": "What auth work is in flight?"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["answer"], str) and body["answer"]
    assert len(body["citations"]) > 0


# ---- 6.5 Risk model -------------------------------------------------------


@pytest.mark.asyncio
async def test_risk_forecast_low_for_healthy_project(client):
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    pid = proj.json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}/risk-forecast")
    assert resp.status_code == 200
    body = resp.json()
    assert 0 <= body["p_slip_1w"] <= 0.5
    assert body["p_slip_1w"] <= body["p_slip_4w"]


@pytest.mark.asyncio
async def test_risk_forecast_rises_with_overdue(client):
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    pid = proj.json()["id"]
    yesterday = (date.today() - timedelta(days=2)).isoformat()
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
    resp = await client.get(f"/api/v1/projects/{pid}/risk-forecast")
    body = resp.json()
    assert body["p_slip_1w"] > 0.5
    assert any("overdue" in f.lower() for f in body["top_factors"])


# ---- 6.4 Resource leveling -----------------------------------------------


@pytest.mark.asyncio
async def test_resource_leveling_fills_unassigned(client):
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    pid = proj.json()["id"]
    for i in range(4):
        await client.post(
            "/api/v1/tasks/",
            json={"project_id": pid, "title": f"T{i}", "estimated_hours": 8},
        )
    resp = await client.post(
        f"/api/v1/projects/{pid}/optimize-resources",
        json={"team": ["alice", "bob"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    # All 4 unassigned tasks should get a suggested_assignee.
    assignees = [s["suggested_assignee"] for s in body["suggestions"]]
    assert set(assignees).issubset({"alice", "bob"})
    assert all(a is not None for a in assignees)
    # Load should be balanced — both members should have non-zero load.
    assert body["load_after"]["alice"] > 0
    assert body["load_after"]["bob"] > 0


# ---- 6.6 Billing ----------------------------------------------------------


@pytest.mark.asyncio
async def test_billing_records_and_lists_usage(client):
    rec = await client.post(
        "/api/v1/billing/usage", json={"metric": "ai_call", "quantity": 3}
    )
    assert rec.status_code == 200
    usage = (await client.get("/api/v1/billing/usage")).json()
    assert len(usage) == 1
    assert usage[0]["metric"] == "ai_call"
    assert usage[0]["quantity"] == 3


@pytest.mark.asyncio
async def test_billing_portal_returns_stub_url(client):
    resp = await client.post("/api/v1/billing/portal")
    body = resp.json()
    assert body["stub"] is True
    assert "billing-portal" in body["url"]


@pytest.mark.asyncio
async def test_billing_usage_isolated_per_workspace(client, second_client):
    await client.post("/api/v1/billing/usage", json={"metric": "x"})
    bob = (await second_client.get("/api/v1/billing/usage")).json()
    assert bob == []


# ---- 6.7 Slack + GitHub stubs --------------------------------------------


@pytest.mark.asyncio
async def test_slack_notify_stub(client):
    resp = await client.post(
        "/api/v1/integrations/slack/notify",
        json={"channel": "#eng", "text": "Hello team"},
    )
    assert resp.json() == {"channel": "#eng", "text": "Hello team", "stub": True}


@pytest.mark.asyncio
async def test_github_issue_stub(client):
    resp = await client.post(
        "/api/v1/integrations/github/issues",
        json={"repo": "dclawstack/dclaw-project", "title": "Bug", "body": "..."},
    )
    body = resp.json()
    assert body["number"] == 1
    listed = (await client.get("/api/v1/integrations/github/issues")).json()
    assert len(listed) == 1


# ---- 6.8 Logto stub -------------------------------------------------------


@pytest.mark.asyncio
async def test_logto_validate_accepts_stub_token(client):
    resp = await client.post(
        "/api/v1/integrations/logto/validate",
        json={"token": "stub.alice@example.com"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_logto_validate_rejects_garbage(client):
    resp = await client.post(
        "/api/v1/integrations/logto/validate",
        json={"token": "not-a-real-jwt"},
    )
    assert resp.status_code == 401


# ---- 6.9 Document upload --------------------------------------------------


@pytest.mark.asyncio
async def test_upload_document(client, tmp_path, monkeypatch):
    monkeypatch.setenv("DCLAW_DOCS_DIR", str(tmp_path))
    files = {"file": ("brief.txt", io.BytesIO(b"Project brief: ship the auth flow."), "text/plain")}
    resp = await client.post("/api/v1/documents/", files=files)
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "brief.txt"
    assert body["size_bytes"] > 0

    listed = (await client.get("/api/v1/documents/")).json()
    assert len(listed) == 1


@pytest.mark.asyncio
async def test_documents_isolated_per_workspace(client, second_client, tmp_path, monkeypatch):
    monkeypatch.setenv("DCLAW_DOCS_DIR", str(tmp_path))
    files = {"file": ("a.txt", io.BytesIO(b"alice's doc"), "text/plain")}
    await client.post("/api/v1/documents/", files=files)
    bob = (await second_client.get("/api/v1/documents/")).json()
    assert bob == []


# ---- 6.10 Sprints ---------------------------------------------------------


@pytest.mark.asyncio
async def test_sprint_create_and_add_tasks(client):
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    pid = proj.json()["id"]
    t1 = await client.post("/api/v1/tasks/", json={"project_id": pid, "title": "T1"})
    t2 = await client.post("/api/v1/tasks/", json={"project_id": pid, "title": "T2"})

    sprint = await client.post(
        "/api/v1/sprints/",
        json={
            "project_id": pid,
            "name": "Sprint 1",
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=14)),
            "capacity_hours": 80,
        },
    )
    assert sprint.status_code == 201
    sid = sprint.json()["id"]

    add = await client.post(
        f"/api/v1/sprints/{sid}/tasks",
        json={"task_ids": [t1.json()["id"], t2.json()["id"]]},
    )
    assert add.status_code == 200
    assert len(add.json()["task_ids"]) == 2

    listed = await client.get(f"/api/v1/sprints/?project_id={pid}")
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_sprint_rejects_inverted_dates(client):
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    pid = proj.json()["id"]
    resp = await client.post(
        "/api/v1/sprints/",
        json={
            "project_id": pid,
            "name": "Bad",
            "start_date": str(date.today()),
            "end_date": str(date.today() - timedelta(days=1)),
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_sprint_isolated_per_workspace(client, second_client):
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    pid = proj.json()["id"]
    sprint = await client.post(
        "/api/v1/sprints/",
        json={
            "project_id": pid,
            "name": "S",
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=7)),
        },
    )
    sid = sprint.json()["id"]
    resp = await second_client.get(f"/api/v1/sprints/{sid}")
    assert resp.status_code == 404
