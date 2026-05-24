from uuid import UUID
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthContext, require_workspace
from app.repositories.project_repo import ProjectRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.time_entry_repo import TimeEntryRepository
from app.schemas.time_entry import (
    TimeEntryManual,
    TimeEntryRead,
    TimeEntryStart,
    TimeEntryUpdate,
    TimeSummary,
)
from app.models.time_entry import TimeEntry

router = APIRouter()


async def _task_in_workspace(
    db: AsyncSession, task_id: UUID, ctx: AuthContext
):
    task = await TaskRepository(db).get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    project = await ProjectRepository(db).get_by_id_in_workspace(
        task.project_id, ctx.workspace.id
    )
    if not project:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/start", response_model=TimeEntryRead, status_code=status.HTTP_201_CREATED)
async def start_timer(
    data: TimeEntryStart,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    await _task_in_workspace(db, data.task_id, ctx)
    repo = TimeEntryRepository(db)
    # One active timer per user. Stop any pre-existing one cleanly.
    active = await repo.active_for_user(ctx.user.id)
    if active:
        now = _now()
        active.ended_at = now
        active.duration_seconds = max(
            0, int((now - _normalize_aware(active.started_at)).total_seconds())
        )
        await db.commit()

    entry = TimeEntry(
        task_id=data.task_id,
        user_id=ctx.user.id,
        started_at=_now(),
        notes=data.notes,
        billable=data.billable,
    )
    return await repo.create(entry)


def _normalize_aware(dt: datetime) -> datetime:
    """SQLite stores naive datetimes — coerce to UTC-aware for math."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.post("/stop", response_model=TimeEntryRead)
async def stop_timer(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    repo = TimeEntryRepository(db)
    active = await repo.active_for_user(ctx.user.id)
    if not active:
        raise HTTPException(status_code=404, detail="No active timer")
    now = _now()
    active.ended_at = now
    active.duration_seconds = max(
        0, int((now - _normalize_aware(active.started_at)).total_seconds())
    )
    await db.commit()
    await db.refresh(active)
    return active


@router.get("/active", response_model=TimeEntryRead | None)
async def get_active_timer(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    return await TimeEntryRepository(db).active_for_user(ctx.user.id)


@router.post(
    "/manual", response_model=TimeEntryRead, status_code=status.HTTP_201_CREATED
)
async def manual_time_entry(
    data: TimeEntryManual,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    await _task_in_workspace(db, data.task_id, ctx)
    if data.ended_at <= data.started_at:
        raise HTTPException(status_code=400, detail="ended_at must be after started_at")
    duration = max(
        0,
        int(
            (_normalize_aware(data.ended_at) - _normalize_aware(data.started_at)).total_seconds()
        ),
    )
    entry = TimeEntry(
        task_id=data.task_id,
        user_id=ctx.user.id,
        started_at=data.started_at,
        ended_at=data.ended_at,
        duration_seconds=duration,
        notes=data.notes,
        billable=data.billable,
    )
    return await TimeEntryRepository(db).create(entry)


@router.get("/task/{task_id}", response_model=List[TimeEntryRead])
async def list_entries_for_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    await _task_in_workspace(db, task_id, ctx)
    return await TimeEntryRepository(db).list_for_task(task_id)


@router.get("/task/{task_id}/summary", response_model=TimeSummary)
async def task_time_summary(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    await _task_in_workspace(db, task_id, ctx)
    total, billable, entries = await TimeEntryRepository(db).summary_for_task(task_id)
    return TimeSummary(
        task_id=task_id,
        total_seconds=total,
        billable_seconds=billable,
        entries=entries,
    )


@router.put("/{entry_id}", response_model=TimeEntryRead)
async def update_time_entry(
    entry_id: UUID,
    data: TimeEntryUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    repo = TimeEntryRepository(db)
    entry = await repo.get_by_id(entry_id)
    if not entry or entry.user_id != ctx.user.id:
        raise HTTPException(status_code=404, detail="Time entry not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    if entry.ended_at and entry.started_at:
        entry.duration_seconds = max(
            0,
            int(
                (_normalize_aware(entry.ended_at) - _normalize_aware(entry.started_at)).total_seconds()
            ),
        )
    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_time_entry(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    repo = TimeEntryRepository(db)
    entry = await repo.get_by_id(entry_id)
    if not entry or entry.user_id != ctx.user.id:
        raise HTTPException(status_code=404, detail="Time entry not found")
    await repo.hard_delete(entry)
    return None
