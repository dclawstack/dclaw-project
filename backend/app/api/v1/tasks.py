from uuid import UUID
from typing import List
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthContext, require_workspace
from app.repositories.task_repo import TaskRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.tag_repo import TagRepository
from app.repositories.comment_repo import CommentRepository
from app.schemas.task import (
    TaskCreate,
    TaskRead,
    TaskUpdate,
    TaskListResponse,
    TaskBulkRequest,
)
from app.schemas.comment import CommentCreate, CommentRead, CommentUpdate
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.comment import Comment
from app.services.notifier import (
    notify_task_assigned,
    notify_task_comment,
    notify_task_completed,
    publish_entity_event,
)

router = APIRouter()


def _set_completed_at(task: Task, *, was_done: bool) -> None:
    """Stamp completion date when a task TRANSITIONS into done.

    `was_done` is the status snapshot from BEFORE the patch was applied,
    so the caller can tell us whether this is the first done-transition
    in this request. On every done-transition (including re-completion
    of a reopened task) we re-stamp completed_at to today so burndown
    and velocity reflect when the work was actually finished.

    When status moves OFF done we leave completed_at intact — it
    records the most recent completion timestamp.
    """
    if task.status == TaskStatus.done and not was_done:
        task.completed_at = date.today()


async def _project_in_workspace(
    db: AsyncSession, project_id: UUID, ctx: AuthContext
):
    project = await ProjectRepository(db).get_by_id_in_workspace(
        project_id, ctx.workspace.id
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _task_in_workspace(
    db: AsyncSession, task_id: UUID, ctx: AuthContext
) -> Task:
    task = await TaskRepository(db).get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    # Ensure the task's project is in the caller's workspace.
    await _project_in_workspace(db, task.project_id, ctx)
    return task


@router.get(
    "/",
    response_model=TaskListResponse,
    summary="List tasks (scoped to the active workspace) with search/filter/pagination",
)
async def list_tasks(
    q: str | None = Query(default=None),
    project_id: UUID | None = Query(default=None),
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = Query(default=None),
    assignee: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    parent_task_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    repo = TaskRepository(db)
    items, total = await repo.search(
        workspace_id=ctx.workspace.id,
        project_id=project_id,
        parent_task_id=parent_task_id,
        q=q,
        status=status_filter,
        priority=priority,
        assignee=assignee,
        tag=tag,
        limit=limit,
        offset=offset,
    )
    return TaskListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    await _project_in_workspace(db, data.project_id, ctx)
    if data.parent_task_id is not None:
        parent = await TaskRepository(db).get_by_id(data.parent_task_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent task not found")
        if parent.project_id != data.project_id:
            raise HTTPException(
                status_code=400, detail="Parent task must belong to the same project"
            )

    repo = TaskRepository(db)
    tag_repo = TagRepository(db)
    payload = data.model_dump(exclude={"tag_ids"})
    task = Task(**payload)
    # Fresh task: was_done=False so creating with status=done stamps today.
    _set_completed_at(task, was_done=False)
    if data.tag_ids:
        task.tags = await tag_repo.get_many_in_workspace(
            data.tag_ids, ctx.workspace.id
        )
    created = await repo.create(task)

    publish_entity_event(
        workspace_id=ctx.workspace.id,
        kind="task.created",
        payload={"task_id": str(created.id), "project_id": str(created.project_id)},
    )
    if created.assignee:
        await notify_task_assigned(
            db, workspace_id=ctx.workspace.id, actor_id=ctx.user.id, task=created
        )
    return created


@router.get("/stats/due-today", response_model=List[TaskRead])
async def tasks_due_today(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    repo = TaskRepository(db)
    return await repo.list_due_today(date.today(), workspace_id=ctx.workspace.id)


@router.get("/stats/overdue", response_model=List[TaskRead])
async def tasks_overdue(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    repo = TaskRepository(db)
    return await repo.list_overdue(date.today(), workspace_id=ctx.workspace.id)


@router.get("/stats/completed-count")
async def completed_tasks_count(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    repo = TaskRepository(db)
    count = await repo.count_by_status(TaskStatus.done, workspace_id=ctx.workspace.id)
    return {"count": count}


@router.post("/bulk", response_model=List[TaskRead])
async def bulk_update_tasks(
    data: TaskBulkRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    repo = TaskRepository(db)
    tasks = await repo.get_many(data.ids)
    # Drop anything outside the caller's workspace before the lookup-missing
    # check so we don't leak the existence of tasks in other tenants.
    project_repo = ProjectRepository(db)
    in_scope: list[Task] = []
    for t in tasks:
        proj = await project_repo.get_by_id_in_workspace(t.project_id, ctx.workspace.id)
        if proj is not None:
            in_scope.append(t)
    found_ids = {t.id for t in in_scope}
    missing = [i for i in data.ids if i not in found_ids]
    if missing:
        raise HTTPException(
            status_code=404, detail=f"Tasks not found: {[str(m) for m in missing]}"
        )
    patch = data.patch.model_dump(exclude_unset=True)
    status_in_patch = "status" in patch
    for t in in_scope:
        was_done = t.status == TaskStatus.done
        for field, value in patch.items():
            setattr(t, field, value)
        if status_in_patch:
            _set_completed_at(t, was_done=was_done)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    for t in in_scope:
        await db.refresh(t)
    return in_scope


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    return await _task_in_workspace(db, task_id, ctx)


@router.put("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: UUID,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    task = await _task_in_workspace(db, task_id, ctx)
    repo = TaskRepository(db)
    tag_repo = TagRepository(db)
    if data.project_id is not None and data.project_id != task.project_id:
        await _project_in_workspace(db, data.project_id, ctx)
        # Reparenting a task to a different project while it still has
        # subtasks would split the subtree across projects. Block it —
        # callers should explicitly move the subtree first (or just
        # not move tasks across projects, which is the common case).
        # Explicit COUNT query (rather than `task.subtasks` lazy access)
        # so the check works without re-entering the relationship loader
        # in an unsafe async context.
        from sqlalchemy import select as _select, func as _func

        subtask_count = (
            await db.execute(
                _select(_func.count())
                .select_from(Task)
                .where(
                    Task.parent_task_id == task.id,
                    Task.deleted_at.is_(None),
                )
            )
        ).scalar() or 0
        if subtask_count:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot change project_id on a task that has subtasks. "
                    "Move or detach the subtasks first."
                ),
            )
    if data.parent_task_id is not None:
        if data.parent_task_id == task_id:
            raise HTTPException(status_code=400, detail="A task cannot be its own parent")
        parent = await repo.get_by_id(data.parent_task_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent task not found")
        effective_project_id = data.project_id if data.project_id is not None else task.project_id
        if parent.project_id != effective_project_id:
            raise HTTPException(
                status_code=400,
                detail="Parent task must belong to the same project",
            )

    payload = data.model_dump(exclude_unset=True)
    tag_ids = payload.pop("tag_ids", None)
    status_changed = "status" in payload
    # "assignee in payload" alone covers null→someone, someone→null, and
    # someone→someone-else. We compare to the existing value so an idempotent
    # PUT with the same assignee doesn't spam notifications.
    assignee_changed = (
        "assignee" in payload and payload["assignee"] != task.assignee
    )
    previous_status = task.status
    was_done = task.status == TaskStatus.done
    for field, value in payload.items():
        setattr(task, field, value)
    if tag_ids is not None:
        task.tags = await tag_repo.get_many_in_workspace(
            tag_ids, ctx.workspace.id
        )
    if status_changed:
        _set_completed_at(task, was_done=was_done)
    await db.commit()
    await db.refresh(task)

    publish_entity_event(
        workspace_id=ctx.workspace.id,
        kind="task.updated",
        payload={"task_id": str(task.id), "project_id": str(task.project_id)},
    )
    # Only notify when there's actually a new assignee to ping — the
    # unassign case (someone → null) has no recipient.
    if assignee_changed and task.assignee:
        await notify_task_assigned(
            db, workspace_id=ctx.workspace.id, actor_id=ctx.user.id, task=task
        )
    if status_changed and task.status == TaskStatus.done and previous_status != TaskStatus.done:
        await notify_task_completed(
            db, workspace_id=ctx.workspace.id, actor_id=ctx.user.id, task=task
        )
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    task = await _task_in_workspace(db, task_id, ctx)
    await TaskRepository(db).delete(task)
    publish_entity_event(
        workspace_id=ctx.workspace.id,
        kind="task.deleted",
        payload={"task_id": str(task.id), "project_id": str(task.project_id)},
    )
    return None


@router.get("/{task_id}/subtasks", response_model=List[TaskRead])
async def list_subtasks(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    parent = await _task_in_workspace(db, task_id, ctx)
    repo = TaskRepository(db)
    items, _ = await repo.search(
        workspace_id=ctx.workspace.id,
        parent_task_id=task_id,
        limit=500,
        offset=0,
    )
    return items


@router.get("/{task_id}/comments", response_model=List[CommentRead])
async def list_task_comments(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    await _task_in_workspace(db, task_id, ctx)
    items, _ = await CommentRepository(db).list_for_task(task_id, limit=500, offset=0)
    return items


@router.post(
    "/{task_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_task_comment(
    task_id: UUID,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    task = await _task_in_workspace(db, task_id, ctx)
    comment_repo = CommentRepository(db)
    comment = Comment(task_id=task_id, **data.model_dump())
    created = await comment_repo.create(comment)
    await notify_task_comment(
        db,
        workspace_id=ctx.workspace.id,
        actor_id=ctx.user.id,
        task=task,
        comment_body=created.body,
    )
    return created


@router.put("/comments/{comment_id}", response_model=CommentRead)
async def update_task_comment(
    comment_id: UUID,
    data: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    repo = CommentRepository(db)
    comment = await repo.get_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    await _task_in_workspace(db, comment.task_id, ctx)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(comment, field, value)
    await db.commit()
    await db.refresh(comment)
    return comment


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_comment(
    comment_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    repo = CommentRepository(db)
    comment = await repo.get_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    await _task_in_workspace(db, comment.task_id, ctx)
    await repo.hard_delete(comment)
    return None
