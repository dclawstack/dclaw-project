from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthContext, require_workspace
from app.repositories.project_repo import ProjectRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.task_dependency_repo import TaskDependencyRepository
from app.schemas.task_dependency import (
    CriticalPathRead,
    ScheduledTaskRead,
    TaskDependencyCreate,
    TaskDependencyRead,
)
from app.services.task_graph import compute_critical_path, would_cycle
from app.models.task_dependency import TaskDependency

router = APIRouter()  # mounted under /api/v1/tasks
project_scoped_router = APIRouter()  # mounted under /api/v1/projects


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


@router.get("/{task_id}/dependencies", response_model=List[TaskDependencyRead])
async def list_dependencies(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    await _task_in_workspace(db, task_id, ctx)
    return await TaskDependencyRepository(db).list_for_task(task_id)


@router.post(
    "/{task_id}/dependencies",
    response_model=TaskDependencyRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_dependency(
    task_id: UUID,
    data: TaskDependencyCreate,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    task = await _task_in_workspace(db, task_id, ctx)
    if data.depends_on_task_id == task_id:
        raise HTTPException(status_code=400, detail="A task cannot depend on itself")

    prereq = await TaskRepository(db).get_by_id(data.depends_on_task_id)
    if not prereq:
        raise HTTPException(status_code=404, detail="Prerequisite task not found")
    if prereq.project_id != task.project_id:
        raise HTTPException(
            status_code=400,
            detail="Dependencies must be within the same project",
        )

    # Cycle check uses the project-wide dependency graph.
    repo = TaskDependencyRepository(db)
    project_deps = await repo.list_for_project(task.project_id)
    if would_cycle(task_id, data.depends_on_task_id, project_deps):
        raise HTTPException(
            status_code=409,
            detail="Adding this dependency would create a cycle",
        )

    dep = TaskDependency(
        task_id=task_id,
        depends_on_task_id=data.depends_on_task_id,
        type=data.type,
    )
    return await repo.create(dep)


@router.delete(
    "/dependencies/{dependency_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_dependency(
    dependency_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    repo = TaskDependencyRepository(db)
    dep = await repo.get_by_id(dependency_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Dependency not found")
    # Ensure caller can see one of the endpoints.
    await _task_in_workspace(db, dep.task_id, ctx)
    await repo.hard_delete(dep)
    return None


# Project-scoped: critical path & dependency listing


async def _project_in_workspace(
    db: AsyncSession, project_id: UUID, ctx: AuthContext
):
    project = await ProjectRepository(db).get_by_id_in_workspace(
        project_id, ctx.workspace.id
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@project_scoped_router.get(
    "/{project_id}/dependencies", response_model=List[TaskDependencyRead]
)
async def list_project_dependencies(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    await _project_in_workspace(db, project_id, ctx)
    return await TaskDependencyRepository(db).list_for_project(project_id)


@project_scoped_router.get(
    "/{project_id}/critical-path", response_model=CriticalPathRead
)
async def project_critical_path(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    project = await _project_in_workspace(db, project_id, ctx)
    tasks = list(project.active_tasks)
    deps = await TaskDependencyRepository(db).list_for_project(project_id)
    report = compute_critical_path(tasks, deps)
    return CriticalPathRead(
        project_id=project_id,
        total_duration_days=report.total_duration_days,
        critical_chain=report.critical_chain,
        schedule=[ScheduledTaskRead(**s.__dict__) for s in report.schedule],
        cycles_detected=report.cycles_detected,
    )
