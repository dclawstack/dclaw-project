from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.milestone_repo import MilestoneRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.milestone import MilestoneCreate, MilestoneRead, MilestoneUpdate
from app.models.milestone import Milestone

router = APIRouter()


@router.get("/", response_model=List[MilestoneRead])
async def list_milestones(db: AsyncSession = Depends(get_db)):
    repo = MilestoneRepository(db)
    milestones, _ = await repo.list_all(limit=1000, offset=0)
    return milestones


@router.post("/", response_model=MilestoneRead, status_code=status.HTTP_201_CREATED)
async def create_milestone(data: MilestoneCreate, db: AsyncSession = Depends(get_db)):
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(data.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    repo = MilestoneRepository(db)
    milestone = Milestone(**data.model_dump())
    return await repo.create(milestone)


@router.get("/{milestone_id}", response_model=MilestoneRead)
async def get_milestone(milestone_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = MilestoneRepository(db)
    milestone = await repo.get_by_id(milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return milestone


@router.put("/{milestone_id}", response_model=MilestoneRead)
async def update_milestone(milestone_id: UUID, data: MilestoneUpdate, db: AsyncSession = Depends(get_db)):
    repo = MilestoneRepository(db)
    milestone = await repo.get_by_id(milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    if data.project_id is not None:
        project_repo = ProjectRepository(db)
        project = await project_repo.get_by_id(data.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(milestone, field, value)
    await db.commit()
    await db.refresh(milestone)
    return milestone


@router.delete("/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_milestone(milestone_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = MilestoneRepository(db)
    milestone = await repo.get_by_id(milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    await repo.delete(milestone)
    return None
