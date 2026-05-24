from uuid import UUID
from typing import List
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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

router = APIRouter()


def _set_completed_at(task: Task) -> None:
    """Stamp completion date when a task first reaches done.

    Caller must only invoke this when `status` actually changed (so we don't
    wipe history on unrelated edits). When status moves OFF done we leave
    completed_at intact — it records when the work was finished, even if the
    task is later reopened. The next done-transition will re-stamp it.
    """
    if task.status == TaskStatus.done and task.completed_at is None:
        task.completed_at = date.today()


@router.get("/", response_model=TaskListResponse, summary="List tasks with search/filter/pagination")
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
):
    repo = TaskRepository(db)
    items, total = await repo.search(
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
async def create_task(data: TaskCreate, db: AsyncSession = Depends(get_db)):
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(data.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
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
    _set_completed_at(task)
    if data.tag_ids:
        task.tags = await tag_repo.get_many(data.tag_ids)
    return await repo.create(task)


@router.get("/stats/due-today", response_model=List[TaskRead])
async def tasks_due_today(db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    return await repo.list_due_today(date.today())


@router.get("/stats/overdue", response_model=List[TaskRead])
async def tasks_overdue(db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    return await repo.list_overdue(date.today())


@router.get("/stats/completed-count")
async def completed_tasks_count(db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    count = await repo.count_by_status(TaskStatus.done)
    return {"count": count}


@router.post("/bulk", response_model=List[TaskRead])
async def bulk_update_tasks(data: TaskBulkRequest, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    tasks = await repo.get_many(data.ids)
    found_ids = {t.id for t in tasks}
    missing = [i for i in data.ids if i not in found_ids]
    if missing:
        raise HTTPException(
            status_code=404, detail=f"Tasks not found: {[str(m) for m in missing]}"
        )
    patch = data.patch.model_dump(exclude_unset=True)
    status_in_patch = "status" in patch
    for t in tasks:
        for field, value in patch.items():
            setattr(t, field, value)
        if status_in_patch:
            _set_completed_at(t)
    try:
        await db.commit()
    except Exception:
        # Without rollback the session is left in PendingRollbackError state
        # and subsequent operations on it (including the refresh loop below
        # or any later request reusing this session) blow up cryptically.
        await db.rollback()
        raise
    for t in tasks:
        await db.refresh(t)
    return tasks


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=TaskRead)
async def update_task(task_id: UUID, data: TaskUpdate, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    tag_repo = TagRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if data.project_id is not None:
        project = await ProjectRepository(db).get_by_id(data.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    if data.parent_task_id is not None:
        if data.parent_task_id == task_id:
            raise HTTPException(status_code=400, detail="A task cannot be its own parent")
        parent = await repo.get_by_id(data.parent_task_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent task not found")
        # The parent must live in the same project as this task (after any
        # project_id change in this same patch). create_task enforces this
        # symmetry — keep update_task in lockstep so the tree never bridges
        # projects.
        effective_project_id = data.project_id if data.project_id is not None else task.project_id
        if parent.project_id != effective_project_id:
            raise HTTPException(
                status_code=400,
                detail="Parent task must belong to the same project",
            )

    payload = data.model_dump(exclude_unset=True)
    tag_ids = payload.pop("tag_ids", None)
    status_changed = "status" in payload
    for field, value in payload.items():
        setattr(task, field, value)
    if tag_ids is not None:
        task.tags = await tag_repo.get_many(tag_ids)
    if status_changed:
        _set_completed_at(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await repo.delete(task)
    return None


@router.get("/{task_id}/subtasks", response_model=List[TaskRead])
async def list_subtasks(task_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    parent = await repo.get_by_id(task_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Task not found")
    items, _ = await repo.search(parent_task_id=task_id, limit=500, offset=0)
    return items


@router.get("/{task_id}/comments", response_model=List[CommentRead])
async def list_task_comments(task_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    comment_repo = CommentRepository(db)
    items, _ = await comment_repo.list_for_task(task_id, limit=500, offset=0)
    return items


@router.post(
    "/{task_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_task_comment(
    task_id: UUID, data: CommentCreate, db: AsyncSession = Depends(get_db)
):
    repo = TaskRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    comment_repo = CommentRepository(db)
    comment = Comment(task_id=task_id, **data.model_dump())
    return await comment_repo.create(comment)


@router.put("/comments/{comment_id}", response_model=CommentRead)
async def update_task_comment(
    comment_id: UUID, data: CommentUpdate, db: AsyncSession = Depends(get_db)
):
    repo = CommentRepository(db)
    comment = await repo.get_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(comment, field, value)
    await db.commit()
    await db.refresh(comment)
    return comment


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_comment(comment_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = CommentRepository(db)
    comment = await repo.get_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    await repo.hard_delete(comment)
    return None
