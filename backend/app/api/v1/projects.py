from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.project_repo import ProjectRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.milestone_repo import MilestoneRepository
from app.repositories.tag_repo import TagRepository
from app.schemas.project import (
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    ProjectDetailRead,
    ProjectListResponse,
    ProjectStatsResponse,
)
from app.schemas.task import TaskRead
from app.schemas.milestone import MilestoneRead
from app.models.project import Project, ProjectStatus
from app.models.task import TaskStatus

router = APIRouter()


@router.get("/", response_model=ProjectListResponse, summary="List projects with search/filter/pagination")
async def list_projects(
    q: str | None = Query(default=None, description="Search term on name/description"),
    status_filter: ProjectStatus | None = Query(default=None, alias="status"),
    owner: str | None = Query(default=None),
    tag: str | None = Query(default=None, description="Filter by tag name"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    repo = ProjectRepository(db)
    items, total = await repo.search(
        q=q, status=status_filter, owner=owner, tag=tag, limit=limit, offset=offset
    )
    return ProjectListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    repo = ProjectRepository(db)
    tag_repo = TagRepository(db)
    payload = data.model_dump(exclude={"tag_ids"})
    project = Project(**payload)
    if data.tag_ids:
        project.tags = await tag_repo.get_many(data.tag_ids)
    return await repo.create(project)


@router.get("/{project_id}", response_model=ProjectDetailRead)
async def get_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = ProjectRepository(db)
    project = await repo.get_by_id_with_tasks_and_milestones(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    # Serialize from the soft-delete-filtered relationships so tombstoned
    # children don't leak into the public detail payload.
    payload = ProjectRead.model_validate(project).model_dump()
    payload["tasks"] = [TaskRead.model_validate(t).model_dump() for t in project.active_tasks]
    payload["milestones"] = [
        MilestoneRead.model_validate(m).model_dump() for m in project.active_milestones
    ]
    return payload


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: UUID, data: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    repo = ProjectRepository(db)
    tag_repo = TagRepository(db)
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    payload = data.model_dump(exclude_unset=True)
    tag_ids = payload.pop("tag_ids", None)
    for field, value in payload.items():
        setattr(project, field, value)
    if tag_ids is not None:
        project.tags = await tag_repo.get_many(tag_ids)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await repo.delete(project)
    return None


@router.get("/{project_id}/tasks", response_model=List[TaskRead])
async def list_project_tasks(
    project_id: UUID,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    repo = TaskRepository(db)
    tasks, _ = await repo.search(
        project_id=project_id, status=status_filter, limit=limit, offset=offset
    )
    return tasks


@router.get("/{project_id}/milestones", response_model=List[MilestoneRead])
async def list_project_milestones(
    project_id: UUID,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    repo = MilestoneRepository(db)
    milestones, _ = await repo.list_by_project(project_id, limit=limit, offset=offset)
    return milestones


@router.get("/{project_id}/stats", response_model=ProjectStatsResponse)
async def project_stats(project_id: UUID, db: AsyncSession = Depends(get_db)):
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task_repo = TaskRepository(db)
    milestone_repo = MilestoneRepository(db)
    stats = await task_repo.project_stats(project_id)
    m_total, m_completed = await milestone_repo.project_milestone_stats(project_id)
    return ProjectStatsResponse(
        **stats,
        milestone_count=m_total,
        milestone_completed=m_completed,
    )
