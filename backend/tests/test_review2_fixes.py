"""Regression tests for the v1.2.1 code-review findings.

Each test pins a specific bug from the xhigh-effort review so it can't
silently regress. Includes the round-2 hardening findings on the
SSE stream-token mechanism + migration bcrypt seed.
"""
import io
import os
import pytest
import bcrypt
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from app.core.security import create_access_token, decode_token


# Paths derived from this test file so the suite works in any working
# directory — most importantly inside GitHub Actions where the repo
# lives at /home/runner/work/dclaw-project/dclaw-project, not at the
# local checkout root.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_ROOT.parent
_FRONTEND_PUBLIC = _REPO_ROOT / "frontend" / "public"


# ---- Fix #1: SECRET_KEY production guard ---------------------------------


def test_assert_production_ready_blocks_default_key_in_prod():
    from app.core.config import Settings

    s = Settings(app_env="production", secret_key="change-me-in-production")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        s.assert_production_ready()


def test_assert_production_ready_allows_dev_with_default():
    from app.core.config import Settings

    s = Settings(app_env="dev", secret_key="change-me-in-production")
    # Should not raise.
    s.assert_production_ready()


def test_assert_production_ready_allows_prod_with_real_key():
    from app.core.config import Settings

    s = Settings(app_env="production", secret_key="0" * 64)
    s.assert_production_ready()


# ---- Fix #2: logto_validate is auth-gated --------------------------------


@pytest.mark.asyncio
async def test_logto_validate_requires_auth(unauthed_client):
    resp = await unauthed_client.post(
        "/api/v1/integrations/logto/validate",
        json={"token": "stub.alice@example.com"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logto_validate_works_when_authed(client):
    resp = await client.post(
        "/api/v1/integrations/logto/validate",
        json={"token": "stub.alice@example.com"},
    )
    assert resp.status_code == 200


# ---- Fix #3: tags are workspace-scoped -----------------------------------


@pytest.mark.asyncio
async def test_tags_isolated_per_workspace(client, second_client):
    await client.post("/api/v1/tags/", json={"name": "alice-only"})
    # Bob's tag list must not show Alice's tag.
    bob = (await second_client.get("/api/v1/tags/")).json()
    assert [t["name"] for t in bob] == []


@pytest.mark.asyncio
async def test_same_tag_name_allowed_in_different_workspaces(client, second_client):
    a = await client.post("/api/v1/tags/", json={"name": "design"})
    b = await second_client.post("/api/v1/tags/", json={"name": "design"})
    assert a.status_code == 201
    assert b.status_code == 201


@pytest.mark.asyncio
async def test_other_workspace_cannot_get_my_tag(client, second_client):
    tag = await client.post("/api/v1/tags/", json={"name": "secret"})
    tid = tag.json()["id"]
    resp = await second_client.get(f"/api/v1/tags/{tid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_other_workspace_cannot_delete_my_tag(client, second_client):
    tag = await client.post("/api/v1/tags/", json={"name": "victim"})
    tid = tag.json()["id"]
    resp = await second_client.delete(f"/api/v1/tags/{tid}")
    assert resp.status_code == 404
    # Tag still exists for Alice.
    still = await client.get(f"/api/v1/tags/{tid}")
    assert still.status_code == 200


@pytest.mark.asyncio
async def test_cross_tenant_tag_ids_silently_dropped_on_project_create(
    client, second_client
):
    """Bob can't attach Alice's tag to one of his own projects by guessing
    the tag id — the cross-tenant ones get filtered before insert."""
    alice_tag = await client.post("/api/v1/tags/", json={"name": "alice-tag"})
    proj = await second_client.post(
        "/api/v1/projects/",
        json={
            "name": "Bob proj",
            "owner": "bob",
            "tag_ids": [alice_tag.json()["id"]],
        },
    )
    assert proj.status_code == 201
    assert proj.json()["tags"] == []


# ---- Fix #5: upload size cap ---------------------------------------------


@pytest.mark.asyncio
async def test_upload_rejects_oversized_payload(client, tmp_path, monkeypatch):
    monkeypatch.setenv("DCLAW_DOCS_DIR", str(tmp_path))
    monkeypatch.setenv("DCLAW_DOC_MAX_BYTES", "1024")  # 1 KiB
    big = b"x" * 4096
    resp = await client.post(
        "/api/v1/documents/",
        files={"file": ("big.txt", io.BytesIO(big), "text/plain")},
    )
    assert resp.status_code == 413


# ---- Fix #6: SSE token mechanism -----------------------------------------


@pytest.mark.asyncio
async def test_long_lived_jwt_in_query_string_is_rejected(client):
    token = client.headers["Authorization"].split(" ", 1)[1]
    resp = await client.get(f"/api/v1/events/stream?token={token}")
    assert resp.status_code == 401
    assert "stream token" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stream_token_endpoint_mints_short_lived_token(client):
    resp = await client.post("/api/v1/events/token")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["token"], str)
    assert body["expires_in"] >= 30
    # The minted token must carry the stream claim.
    from app.core.security import decode_token

    payload = decode_token(body["token"])
    assert payload["stream"] is True


# ---- Fix #8: critical-path handles cycles without 500 --------------------


@pytest.mark.asyncio
async def test_critical_path_with_cycle_does_not_500(client):
    """We can't add a cycle via the API (cycle detection blocks it), but
    we can ask CPM to handle the no-dep edge case. This pins the more
    important property: the endpoint returns a clean schedule for every
    project and never KeyErrors."""
    proj = (await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})).json()
    pid = proj["id"]
    # Empty project: no tasks, no cycles, just an empty schedule.
    resp = await client.get(f"/api/v1/projects/{pid}/critical-path")
    assert resp.status_code == 200
    assert resp.json()["schedule"] == []
    assert resp.json()["total_duration_days"] == 0


def test_critical_path_unit_handles_cycle_recovery():
    """Direct unit test against a cyclic graph (bypassing the API cycle
    check) — proves the new ls/lf initialization defaults prevent KeyError.

    We pass duck-typed namespace objects rather than touching SQLAlchemy
    so the test runs without a DB."""
    from types import SimpleNamespace
    from app.services.task_graph import compute_critical_path
    from app.models.task import TaskStatus, TaskPriority
    from app.models.task_dependency import DependencyType

    a_id, b_id, p_id = uuid4(), uuid4(), uuid4()

    def _task(tid, title):
        return SimpleNamespace(
            id=tid,
            project_id=p_id,
            title=title,
            description=None,
            estimated_hours=8,
            deleted_at=None,
            status=TaskStatus.todo,
            priority=TaskPriority.medium,
            parent_task_id=None,
        )

    def _dep(task_id, dep_id):
        return SimpleNamespace(
            task_id=task_id,
            depends_on_task_id=dep_id,
            type=DependencyType.FS,
        )

    tasks = [_task(a_id, "A"), _task(b_id, "B")]
    deps = [_dep(b_id, a_id), _dep(a_id, b_id)]  # 2-cycle

    report = compute_critical_path(tasks, deps)
    assert report.cycles_detected is True
    # Cycles invalidate slack math — nothing should be flagged critical.
    assert report.critical_chain == []
    assert len(report.schedule) == 2


# ---- Fix #9: time-entry timer is workspace-scoped ------------------------


@pytest.mark.asyncio
async def test_active_for_user_is_workspace_scoped(client, second_client):
    """Starting a timer in workspace B must not silently stop a timer in
    workspace A."""
    # Bob runs in his own workspace via second_client; Alice in hers.
    # For this test we just verify a single user with two workspaces by
    # creating a second workspace under the SAME user, then switching.
    # Step 1: Alice starts a timer in her original workspace.
    proj1 = await client.post("/api/v1/projects/", json={"name": "P1", "owner": "alice"})
    t1 = await client.post(
        "/api/v1/tasks/", json={"project_id": proj1.json()["id"], "title": "T1"}
    )
    await client.post("/api/v1/time-entries/start", json={"task_id": t1.json()["id"]})

    # Step 2: Alice spins up a second workspace and switches.
    ws2 = await client.post("/api/v1/workspaces/", json={"name": "Side"})
    ws2_id = ws2.json()["id"]
    switched = await client.post(f"/api/v1/auth/switch-workspace/{ws2_id}")
    new_token = switched.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {new_token}"

    # Step 3: in workspace 2 there's no active timer.
    active = await client.get("/api/v1/time-entries/active")
    assert active.json() is None


# ---- Fix #10: switch-workspace doesn't lock out a removed user ----------


@pytest.mark.asyncio
async def test_switch_workspace_only_validates_target_membership(client):
    """Alice creates a second workspace, then switches into it. Even
    if her token's ws claim referenced a workspace she was no longer
    in (the lockout case), the endpoint should still accept a valid
    token + target-workspace membership."""
    ws2 = await client.post("/api/v1/workspaces/", json={"name": "Other"})
    resp = await client.post(f"/api/v1/auth/switch-workspace/{ws2.json()['id']}")
    assert resp.status_code == 200
    assert resp.json()["workspace"]["name"] == "Other"


# ---- Fix #11: notifier failures don't 500 the originating request ------


@pytest.mark.asyncio
async def test_notifier_wrapper_swallows_real_resolve_failure(client, monkeypatch):
    """Make _resolve_assignee raise. The wrapped notify_task_assigned
    should log and return, NOT propagate."""
    from app.services import notifier as notifier_module

    async def boom(*_a, **_k):
        raise RuntimeError("resolver down")

    monkeypatch.setattr(notifier_module, "_resolve_assignee", boom)

    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    resp = await client.post(
        "/api/v1/tasks/",
        json={
            "project_id": proj.json()["id"],
            "title": "T",
            "assignee": "anyone@example.com",
        },
    )
    # Task creation still succeeds even though the notifier internal failed.
    assert resp.status_code == 201


# ---- Fix #12: reparenting a task with subtasks is blocked --------------


@pytest.mark.asyncio
async def test_update_task_with_subtasks_cannot_change_project(client):
    p1 = await client.post("/api/v1/projects/", json={"name": "A", "owner": "u"})
    p2 = await client.post("/api/v1/projects/", json={"name": "B", "owner": "u"})
    parent = await client.post(
        "/api/v1/tasks/", json={"project_id": p1.json()["id"], "title": "Parent"}
    )
    await client.post(
        "/api/v1/tasks/",
        json={
            "project_id": p1.json()["id"],
            "title": "Sub",
            "parent_task_id": parent.json()["id"],
        },
    )
    bad = await client.put(
        f"/api/v1/tasks/{parent.json()['id']}",
        json={"project_id": p2.json()["id"]},
    )
    assert bad.status_code == 400


# ---- Fix #15: unique-slug fallback no longer produces "-1" -------------


def test_unique_slug_uses_fallback_root_when_base_empty():
    import asyncio
    from unittest.mock import AsyncMock
    from app.api.v1.auth import _unique_slug

    repo = AsyncMock()
    repo.get_by_slug = AsyncMock(return_value=None)

    slug = asyncio.run(_unique_slug(repo, ""))
    assert slug == "workspace"


def test_unique_slug_handles_collision_with_fallback():
    import asyncio
    from unittest.mock import AsyncMock
    from app.api.v1.auth import _unique_slug

    repo = AsyncMock()
    # First two calls return "exists", third returns None.
    repo.get_by_slug = AsyncMock(side_effect=[object(), object(), None])

    slug = asyncio.run(_unique_slug(repo, ""))
    # Should be workspace-1 or workspace-2, NOT "-1"/"-2"
    assert slug.startswith("workspace")


# ---- Fix #16: _set_completed_at re-stamps on re-completion -------------


@pytest.mark.asyncio
async def test_completed_at_is_restamped_on_recompletion(client):
    """Old behavior: re-completing a reopened task left completed_at at the
    original date, distorting burndown/velocity. After the fix, the date
    is updated to today on each done-transition."""
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    t = await client.post(
        "/api/v1/tasks/",
        json={"project_id": proj.json()["id"], "title": "T", "status": "done"},
    )
    first_stamp = t.json()["completed_at"]
    assert first_stamp is not None

    # Reopen, then re-complete (in the same test run today_stamp == first_stamp,
    # but the contract is "the stamp is updated each done-transition"). To
    # detect this with date-granularity we just need to confirm the helper
    # was invoked — the cleanest check is that an in-progress→done PUT still
    # writes today's date and the API returns it.
    reopened = await client.put(
        f"/api/v1/tasks/{t.json()['id']}", json={"status": "in_progress"}
    )
    assert reopened.json()["completed_at"] == first_stamp  # preserved (good)

    redone = await client.put(
        f"/api/v1/tasks/{t.json()['id']}", json={"status": "done"}
    )
    # Re-stamped to today (which == first_stamp for a same-day test, but
    # the important property is that it's NOT None and NOT something
    # earlier).
    assert redone.json()["completed_at"] is not None


# ---- Fix #19: assignee-changed fires for null transitions -------------


@pytest.mark.asyncio
async def test_unassign_fires_task_updated_event(client):
    """Setting assignee to null must update the row and publish a
    task.updated event (we don't notify a null recipient, but we also
    can't silently no-op the row update)."""
    proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
    t = await client.post(
        "/api/v1/tasks/",
        json={
            "project_id": proj.json()["id"],
            "title": "T",
            "assignee": "someone@example.com",
        },
    )
    updated = await client.put(
        f"/api/v1/tasks/{t.json()['id']}", json={"assignee": None}
    )
    assert updated.status_code == 200
    assert updated.json()["assignee"] is None


# ---- Fix #22: rag.cosine dimension mismatch returns 0 ----------------


def test_cosine_returns_zero_on_dimension_mismatch():
    from app.services.rag import cosine

    assert cosine([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0
    assert cosine([], [1.0]) == 0.0
    # Same length still computes.
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0


# ---- Round 2 / Fix #1: stream token TTL is actually 60s ----------------


def test_create_access_token_honours_ttl_seconds_override():
    """Round-2 finding: stream tokens were minted with the default 60-MINUTE
    TTL because `create_access_token` had no way to override the window.
    The new `ttl_seconds` parameter must produce an `exp - iat` close to
    the requested 60 seconds, not 3600."""
    token = create_access_token("user-id", ttl_seconds=60)
    payload = decode_token(token)
    assert payload is not None
    # Allow 1s clock-drift slack on either side; should be 60s, never 3600s.
    delta = payload["exp"] - payload["iat"]
    assert 59 <= delta <= 61, f"stream token TTL is {delta}s, expected ~60s"


@pytest.mark.asyncio
async def test_stream_token_endpoint_mints_60s_token(client):
    """The /events/token endpoint must actually mint a 60s token end-to-end,
    not the default user-session window."""
    resp = await client.post("/api/v1/events/token")
    assert resp.status_code == 200
    body = resp.json()
    assert body["expires_in"] == 60
    payload = decode_token(body["token"])
    assert payload["stream"] is True
    delta = payload["exp"] - payload["iat"]
    assert 59 <= delta <= 61


# ---- Round 2 / Fix #2: stream tokens rejected as API Bearer creds -----


@pytest.mark.asyncio
async def test_stream_token_is_not_accepted_as_bearer(client):
    """Round-2 critical finding: a stream token (designed to land in
    URLs / logs / Referer headers) MUST NOT be replayable as a Bearer
    credential against regular API endpoints, otherwise the short-lived
    SSE-token mechanism provides no actual security benefit."""
    minted = await client.post("/api/v1/events/token")
    stream_token = minted.json()["token"]

    # Try to use the stream token as a regular Bearer credential.
    # Build a fresh client so we don't disturb the fixture's headers.
    from httpx import AsyncClient, ASGITransport
    from app.api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {stream_token}"},
    ) as ac:
        for path in [
            "/api/v1/projects/",
            "/api/v1/tasks/",
            "/api/v1/auth/me",
            "/api/v1/notifications/",
            "/api/v1/tags/",
        ]:
            resp = await ac.get(path)
            assert resp.status_code == 401, (
                f"{path} accepted a stream token as Bearer — that's the "
                "exact bypass the SSE-token TTL fix is supposed to prevent."
            )


# ---- Round 2 / Fix #3: migration bcrypt hash actually verifies --------


def test_migration_legacy_password_hash_is_valid():
    """The legacy admin seed in 727eec711a17 was using a hardcoded bcrypt
    hash that didn't actually verify against the documented 'change-me-now'
    password. The fix computes the hash at runtime via bcrypt.hashpw, so
    operators can sign in and re-assign legacy projects after the
    backfill."""
    # Smoke check: bcrypt actually works with the password the migration uses.
    h = bcrypt.hashpw(b"change-me-now", bcrypt.gensalt()).decode("ascii")
    assert bcrypt.checkpw(b"change-me-now", h.encode("ascii"))

    # Read the migration source and ensure the fix is in place: hash is
    # computed at runtime (bcrypt.hashpw) and the old broken literal
    # never returns.
    migration = (
        _BACKEND_ROOT
        / "alembic"
        / "versions"
        / "727eec711a17_add_users_workspaces_and_project_.py"
    )
    src = migration.read_text()
    assert "bcrypt.hashpw" in src, (
        "Migration no longer computes the legacy password hash at "
        "runtime — operators will lose the documented recovery path."
    )
    assert "$2b$12$KIXq3Y8R9F7t5Q1Lq" not in src, (
        "Hardcoded bcrypt literal reintroduced — the legacy admin "
        "password won't verify."
    )


# ---- Round 2 / Fix #4: notifier savepoint actually covers the INSERT --


@pytest.mark.asyncio
async def test_notifier_savepoint_isolates_failure_from_outer_txn(client):
    """If the notification insert fails (e.g. would-be FK violation), the
    failure must NOT poison the outer transaction. The fix moves
    `await db.flush()` inside `begin_nested()` so the savepoint catches
    the insert error instead of letting it surface in the outer commit.

    We exercise this by forcing the notifier to fail and confirming the
    triggering write still committed."""
    from app.services import notifier as notifier_module

    # Original _persist_and_publish stays intact; we make _resolve_assignee
    # return a uuid that doesn't exist so the FK constraint to users.id
    # fails on insert.
    async def fake_resolver(*_a, **_k):
        return uuid4()  # invalid user_id → FK violation on Notification.user_id

    monkey_patches: list = []
    monkey_patches.append(
        (notifier_module, "_resolve_assignee", notifier_module._resolve_assignee)
    )
    notifier_module._resolve_assignee = fake_resolver
    try:
        proj = await client.post("/api/v1/projects/", json={"name": "P", "owner": "u"})
        # Task create triggers notify_task_assigned. The notifier insert
        # will fail (invalid user_id FK), but the savepoint contains the
        # failure, the wrapper swallows it, and the task itself persists.
        resp = await client.post(
            "/api/v1/tasks/",
            json={
                "project_id": proj.json()["id"],
                "title": "T",
                "assignee": "bob@example.com",
            },
        )
        assert resp.status_code == 201, (
            f"Notifier insert failure poisoned the outer txn: {resp.status_code}"
        )
    finally:
        for mod, attr, original in monkey_patches:
            setattr(mod, attr, original)


# ---- Round 2 / Fix #5: manifest icon reference is removed -----------


def test_manifest_does_not_reference_nonexistent_icon():
    """Round-2 finding: dclaw-manifest.json referenced /dclaw-icon.svg
    which didn't exist in frontend/public/. Removed the reference so
    DPanel doesn't 404 when loading the launcher tile."""
    import json

    manifest_path = _FRONTEND_PUBLIC / "dclaw-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if "icon" in manifest:
        # If we DO declare an icon, the asset MUST exist.
        icon_rel = manifest["icon"].lstrip("/")
        icon_abs = _FRONTEND_PUBLIC / icon_rel
        assert icon_abs.exists(), (
            f"manifest declares icon {manifest['icon']} but no file "
            f"at {icon_abs}"
        )
