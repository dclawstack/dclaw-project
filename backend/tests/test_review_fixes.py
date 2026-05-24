"""Regression tests for the code-review findings on the YC-roadmap branch.

Each test pins a specific bug from the review so it can't silently come back.
"""
import pytest
from datetime import date, timedelta


# ---- 1: list_project_tasks accepts TaskStatus and actually filters --------


@pytest.mark.asyncio
async def test_list_project_tasks_filters_by_task_status(client):
    proj = (await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})).json()
    pid = proj["id"]
    for status in ["todo", "in_progress", "done"]:
        await client.post(
            "/api/v1/tasks/",
            json={"project_id": pid, "title": f"T-{status}", "status": status},
        )

    # Valid TaskStatus values must be accepted (previously rejected with 422
    # because the param was typed as ProjectStatus).
    resp = await client.get(f"/api/v1/projects/{pid}/tasks?status=todo")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "T-todo"

    resp = await client.get(f"/api/v1/projects/{pid}/tasks?status=done")
    assert resp.status_code == 200
    assert {t["title"] for t in resp.json()} == {"T-done"}


@pytest.mark.asyncio
async def test_list_project_tasks_rejects_project_status_value(client):
    proj = (await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})).json()
    # `active` is a valid ProjectStatus but NOT a TaskStatus — the endpoint
    # should reject it now (proves the param is correctly typed).
    resp = await client.get(f"/api/v1/projects/{proj['id']}/tasks?status=active")
    assert resp.status_code == 422


# ---- 2 + 3: soft-delete cascades; ProjectDetailRead hides tombstones ------


@pytest.mark.asyncio
async def test_soft_delete_project_hides_its_tasks_and_milestones(client):
    proj = (await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})).json()
    pid = proj["id"]
    t = await client.post("/api/v1/tasks/", json={"project_id": pid, "title": "T"})
    await client.post(
        "/api/v1/milestones/",
        json={"project_id": pid, "name": "M", "target_date": str(date.today())},
    )

    await client.delete(f"/api/v1/projects/{pid}")

    tasks = await client.get("/api/v1/tasks/")
    assert tasks.json()["total"] == 0, "child tasks must be hidden after parent soft-delete"

    overdue = await client.get("/api/v1/tasks/stats/overdue")
    assert overdue.status_code == 200
    # the orphan task (if it leaked through) shouldn't appear on global stats
    assert t.json()["id"] not in [x["id"] for x in overdue.json()]


@pytest.mark.asyncio
async def test_project_detail_hides_soft_deleted_children(client):
    proj = (await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})).json()
    pid = proj["id"]
    keep = await client.post("/api/v1/tasks/", json={"project_id": pid, "title": "keep"})
    drop = await client.post("/api/v1/tasks/", json={"project_id": pid, "title": "drop"})
    await client.delete(f"/api/v1/tasks/{drop.json()['id']}")

    detail = (await client.get(f"/api/v1/projects/{pid}")).json()
    titles = [t["title"] for t in detail["tasks"]]
    assert titles == ["keep"], (
        "ProjectDetailRead must not leak tombstoned tasks"
        f" — got {titles}"
    )


@pytest.mark.asyncio
async def test_soft_delete_parent_task_cascades_to_subtasks(client):
    proj = (await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})).json()
    pid = proj["id"]
    parent = (
        await client.post("/api/v1/tasks/", json={"project_id": pid, "title": "parent"})
    ).json()
    sub = (
        await client.post(
            "/api/v1/tasks/",
            json={"project_id": pid, "title": "sub", "parent_task_id": parent["id"]},
        )
    ).json()

    await client.delete(f"/api/v1/tasks/{parent['id']}")

    # Subtask should also be tombstoned by the cascade.
    resp = await client.get(f"/api/v1/tasks/{sub['id']}")
    assert resp.status_code == 404


# ---- 5: update_task enforces same-project parent --------------------------


@pytest.mark.asyncio
async def test_update_task_rejects_cross_project_parent(client):
    p1 = (await client.post("/api/v1/projects/", json={"name": "A", "owner": "u"})).json()
    p2 = (await client.post("/api/v1/projects/", json={"name": "B", "owner": "u"})).json()
    parent_in_p1 = (
        await client.post(
            "/api/v1/tasks/", json={"project_id": p1["id"], "title": "parent"}
        )
    ).json()
    child_in_p2 = (
        await client.post(
            "/api/v1/tasks/", json={"project_id": p2["id"], "title": "child"}
        )
    ).json()

    bad = await client.put(
        f"/api/v1/tasks/{child_in_p2['id']}",
        json={"parent_task_id": parent_in_p1["id"]},
    )
    assert bad.status_code == 400


# ---- 6: completed_at history is preserved ---------------------------------


@pytest.mark.asyncio
async def test_completed_at_is_preserved_when_reopened(client):
    proj = (await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})).json()
    t = (
        await client.post(
            "/api/v1/tasks/",
            json={"project_id": proj["id"], "title": "T", "status": "done"},
        )
    ).json()
    assert t["completed_at"] is not None
    stamp = t["completed_at"]

    reopened = (
        await client.put(
            f"/api/v1/tasks/{t['id']}", json={"status": "in_progress"}
        )
    ).json()
    # Historical fact preserved — task WAS completed on `stamp`, even though
    # it's now reopened. (Old behavior wiped this silently.)
    assert reopened["completed_at"] == stamp


@pytest.mark.asyncio
async def test_bulk_patch_without_status_does_not_touch_completed_at(client):
    proj = (await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})).json()
    t = (
        await client.post(
            "/api/v1/tasks/",
            json={"project_id": proj["id"], "title": "T", "status": "done"},
        )
    ).json()
    stamp = t["completed_at"]
    assert stamp is not None

    patched = await client.post(
        "/api/v1/tasks/bulk",
        json={"ids": [t["id"]], "patch": {"priority": "urgent"}},
    )
    assert patched.status_code == 200
    assert patched.json()[0]["completed_at"] == stamp


# ---- 9: AI Copilot still works after a programmer-error response ----------


@pytest.mark.asyncio
async def test_copilot_chat_response_shape(client):
    # The chat endpoint should always return 200 with valid fields, even
    # when no provider is configured (heuristic fallback).
    resp = await client.post(
        "/api/v1/ai/copilot/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["text"], str) and data["text"]
    assert data["provider"] in ("heuristic", "openrouter", "ollama")
    assert isinstance(data["model"], str) and data["model"]


# ---- 10: LIKE pattern escaping --------------------------------------------


@pytest.mark.asyncio
async def test_search_treats_percent_as_literal(client):
    proj1 = (await client.post("/api/v1/projects/", json={"name": "Alpha", "owner": "u"})).json()
    await client.post("/api/v1/projects/", json={"name": "Beta", "owner": "u"})

    # `%` is a SQL wildcard. Without escaping, `?q=%` would match every
    # project. With escaping, it should match none (no project contains a
    # literal `%`).
    matched = await client.get("/api/v1/projects/?q=%25")  # URL-encoded `%`
    assert matched.json()["total"] == 0


@pytest.mark.asyncio
async def test_search_treats_underscore_as_literal(client):
    await client.post("/api/v1/projects/", json={"name": "AxB", "owner": "u"})
    await client.post("/api/v1/projects/", json={"name": "A_B", "owner": "u"})

    # `_` is a single-char SQL wildcard. Without escaping `q=A_B` would
    # match `AxB`. With escaping it should match only the literal `A_B`.
    resp = await client.get("/api/v1/projects/?q=A_B")
    titles = [p["name"] for p in resp.json()["items"]]
    assert titles == ["A_B"]


# ---- 13: bulk_update_tasks rollback on commit failure ---------------------


@pytest.mark.asyncio
async def test_bulk_update_rejects_oversized_assignee_before_commit(client):
    """Request-time validation now stops the bad payload before it can
    poison the session. (Belt-and-braces with the explicit rollback added
    in `bulk_update_tasks`.)"""
    proj = (await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})).json()
    t = (
        await client.post(
            "/api/v1/tasks/", json={"project_id": proj["id"], "title": "T"}
        )
    ).json()
    resp = await client.post(
        "/api/v1/tasks/bulk",
        json={"ids": [t["id"]], "patch": {"assignee": "x" * 1000}},
    )
    assert resp.status_code == 422
    # Session is healthy — the next request succeeds.
    follow_up = await client.get("/api/v1/tasks/")
    assert follow_up.status_code == 200


# ---- 11: tag-filter pagination total is correct (DISTINCT count) ----------


@pytest.mark.asyncio
async def test_generate_wbs_is_atomic_when_persistence_fails(client, monkeypatch):
    """If WBS persistence blows up mid-flight, the newly-created project
    must not survive (single-transaction promise). Simulates a failure by
    monkeypatching `milestone_target_date` to raise on its second call,
    after the project + tasks have been staged."""
    from app.api.v1 import ai as ai_router

    call_count = {"n": 0}
    original = ai_router.milestone_target_date

    def fail_on_second_call(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] >= 2:
            raise RuntimeError("simulated persistence failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(ai_router, "milestone_target_date", fail_on_second_call)

    before = (await client.get("/api/v1/projects/")).json()["total"]
    # The ASGI test transport surfaces uncaught exceptions instead of the
    # 500 a real HTTP client would see — catch it so we can assert on the
    # database state, which is the part of the contract we care about.
    with pytest.raises(RuntimeError):
        await client.post(
            "/api/v1/ai/generate-wbs",
            json={
                "goal": "Anything",
                "deadline_days": 10,
                "team_size": 2,
                "project_name": "ShouldNotPersist",
                "owner": "alice",
            },
        )

    after = (await client.get("/api/v1/projects/")).json()["total"]
    assert after == before, (
        "rolled-back transaction must not leave the orphan project behind"
    )


@pytest.mark.asyncio
async def test_generate_wbs_wires_depends_on_into_parent_task_id(client):
    """The WBS generator returns a depends_on graph; the persistence layer
    used to ignore it entirely. After the fix the first dependency of each
    task should land in parent_task_id."""
    resp = await client.post(
        "/api/v1/ai/generate-wbs",
        json={
            "goal": "Anything",
            "deadline_days": 14,
            "team_size": 2,
            "project_name": "P",
            "owner": "alice",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # The fallback template has tasks where index >= 1 all depend on
    # earlier tasks. Verify at least one persisted task got a parent_task_id.
    detail = (await client.get(f"/api/v1/projects/{data['project_id']}")).json()
    titles_with_parent = [
        t["title"] for t in detail["tasks"] if t["parent_task_id"] is not None
    ]
    assert titles_with_parent, (
        "no persisted task has a parent_task_id — the generated dependency"
        " graph was silently dropped"
    )


@pytest.mark.asyncio
async def test_tag_filter_total_matches_unique_items(client):
    t1 = (await client.post("/api/v1/tags/", json={"name": "frontend"})).json()
    t2 = (await client.post("/api/v1/tags/", json={"name": "backend"})).json()
    proj = (
        await client.post(
            "/api/v1/projects/",
            json={"name": "P", "owner": "u", "tag_ids": [t1["id"], t2["id"]]},
        )
    ).json()
    # Create a task with two tags so the JOIN could in principle double-count.
    await client.post(
        "/api/v1/tasks/",
        json={
            "project_id": proj["id"],
            "title": "T",
            "tag_ids": [t1["id"], t2["id"]],
        },
    )
    resp = await client.get("/api/v1/tasks/?tag=frontend")
    body = resp.json()
    assert body["total"] == len(body["items"]) == 1
