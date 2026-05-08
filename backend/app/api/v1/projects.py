from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.project_repo import ProjectRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.milestone_repo import MilestoneRepository
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate, ProjectDetailRead
from app.schemas.task import TaskRead
from app.schemas.milestone import MilestoneRead
from app.models.project import Project

router = APIRouter()


@router.get("/", response_model=List[ProjectRead])
async def list_projects(db: AsyncSession = Depends(get_db)):
    repo = ProjectRepository(db)
    projects, _ = await repo.list_all(limit=1000, offset=0)
    return projects


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    repo = ProjectRepository(db)
    project = Project(**data.model_dump())
    return await repo.create(project)


@router.get("/{project_id}", response_model=ProjectDetailRead)
async def get_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = ProjectRepository(db)
    project = await repo.get_by_id_with_tasks_and_milestones(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(project_id: UUID, data: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
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
async def list_project_tasks(project_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = TaskRepository(db)
    tasks, _ = await repo.list_by_project(project_id, limit=1000, offset=0)
    return tasks


@router.get("/{project_id}/milestones", response_model=List[MilestoneRead])
async def list_project_milestones(project_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = MilestoneRepository(db)
    milestones, _ = await repo.list_by_project(project_id, limit=1000, offset=0)
    return milestones
