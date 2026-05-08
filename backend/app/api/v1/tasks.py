from uuid import UUID
from typing import List
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.task_repo import TaskRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.models.task import Task, TaskStatus

router = APIRouter()


@router.get("/", response_model=List[TaskRead])
async def list_tasks(db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    tasks, _ = await repo.list_all(limit=1000, offset=0)
    return tasks


@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(data: TaskCreate, db: AsyncSession = Depends(get_db)):
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(data.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    repo = TaskRepository(db)
    task = Task(**data.model_dump())
    return await repo.create(task)


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
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if data.project_id is not None:
        project_repo = ProjectRepository(db)
        project = await project_repo.get_by_id(data.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
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
