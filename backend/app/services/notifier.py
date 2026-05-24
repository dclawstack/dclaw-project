"""Emit in-app notifications + publish the corresponding live event.

Every notifier call does two things:
1. Persists a Notification row (so we have a history surface).
2. Publishes the same payload on the EventBus (so any open SSE listener
   refreshes their bell icon immediately).

Failures here MUST NOT block the originating request (e.g. failing to
notify shouldn't fail the task update). Callers should `await emit_*()`
and propagate only HTTP-level errors.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.notification import Notification, NotificationKind
from app.models.task import Task
from app.repositories.user_repo import UserRepository
from app.services.event_bus import get_event_bus

log = get_logger("dclaw.notifier")


async def _resolve_assignee(db: AsyncSession, assignee: str | None) -> UUID | None:
    """Map a Task.assignee free-text value to a user id when possible.

    The task model currently stores assignee as a plain string (email or
    name). We try a couple of cheap resolutions before giving up; failures
    are silent because notification routing is best-effort.
    """
    if not assignee:
        return None
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(assignee.strip().lower())
    return user.id if user else None


async def _persist_and_publish(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    user_id: UUID,
    kind: NotificationKind,
    title: str,
    body: str = "",
    payload: dict | None = None,
) -> None:
    payload = payload or {}
    notif = Notification(
        workspace_id=workspace_id,
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        payload=payload,
    )
    db.add(notif)
    try:
        await db.commit()
        await db.refresh(notif)
    except Exception as exc:  # pragma: no cover - DB hiccup
        await db.rollback()
        log.warning("notifier.persist_failed", error=str(exc))
        return

    get_event_bus().publish(
        workspace_id=workspace_id,
        kind=f"notification.{kind.value}",
        payload={
            "id": str(notif.id),
            "title": title,
            "body": body,
            "kind": kind.value,
            **payload,
        },
    )


async def notify_task_assigned(
    db: AsyncSession, *, workspace_id: UUID, actor_id: UUID, task: Task
) -> None:
    assignee_user_id = await _resolve_assignee(db, task.assignee)
    if not assignee_user_id or assignee_user_id == actor_id:
        return
    await _persist_and_publish(
        db,
        workspace_id=workspace_id,
        user_id=assignee_user_id,
        kind=NotificationKind.task_assigned,
        title=f"Assigned to task: {task.title}",
        body=task.description or "",
        payload={"task_id": str(task.id), "project_id": str(task.project_id)},
    )


async def notify_task_completed(
    db: AsyncSession, *, workspace_id: UUID, actor_id: UUID, task: Task
) -> None:
    """Notify the project owner (best effort)."""
    from app.repositories.project_repo import ProjectRepository

    project = await ProjectRepository(db).get_by_id(task.project_id)
    if not project:
        return
    owner_id = await _resolve_assignee(db, project.owner)
    if not owner_id or owner_id == actor_id:
        return
    await _persist_and_publish(
        db,
        workspace_id=workspace_id,
        user_id=owner_id,
        kind=NotificationKind.task_completed,
        title=f"Task completed: {task.title}",
        payload={"task_id": str(task.id), "project_id": str(task.project_id)},
    )


async def notify_task_comment(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    task: Task,
    comment_body: str,
) -> None:
    """Ping the task assignee when somebody else comments on their task."""
    assignee_user_id = await _resolve_assignee(db, task.assignee)
    if not assignee_user_id or assignee_user_id == actor_id:
        return
    await _persist_and_publish(
        db,
        workspace_id=workspace_id,
        user_id=assignee_user_id,
        kind=NotificationKind.task_comment,
        title=f"New comment on {task.title}",
        body=comment_body[:300],
        payload={"task_id": str(task.id), "project_id": str(task.project_id)},
    )


def publish_entity_event(
    *, workspace_id: UUID, kind: str, payload: dict
) -> None:
    """Fire a lightweight EventBus message that's not persisted as a
    notification — used for kanban-card moves, task creations, etc.
    """
    get_event_bus().publish(workspace_id=workspace_id, kind=kind, payload=payload)
