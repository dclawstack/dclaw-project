from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthContext, require_workspace
from app.repositories.milestone_repo import MilestoneRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.milestone import MilestoneCreate, MilestoneRead, MilestoneUpdate
from app.models.milestone import Milestone

router = APIRouter()


async def _project_in_workspace(db: AsyncSession, project_id: UUID, ctx: AuthContext):
    project = await ProjectRepository(db).get_by_id_in_workspace(
        project_id, ctx.workspace.id
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _milestone_in_workspace(
    db: AsyncSession, milestone_id: UUID, ctx: AuthContext
) -> Milestone:
    m = await MilestoneRepository(db).get_by_id(milestone_id)
    if not m:
        raise HTTPException(status_code=404, detail="Milestone not found")
    await _project_in_workspace(db, m.project_id, ctx)
    return m


@router.get("", response_model=List[MilestoneRead])
async def list_milestones(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    # Return milestones across all projects in the active workspace.
    proj_repo = ProjectRepository(db)
    projects, _ = await proj_repo.search(workspace_id=ctx.workspace.id, limit=1000, offset=0)
    if not projects:
        return []
    repo = MilestoneRepository(db)
    out: list[Milestone] = []
    for p in projects:
        items, _ = await repo.list_by_project(p.id, limit=1000, offset=0)
        out.extend(items)
    return out


@router.post("", response_model=MilestoneRead, status_code=status.HTTP_201_CREATED)
async def create_milestone(
    data: MilestoneCreate,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    await _project_in_workspace(db, data.project_id, ctx)
    repo = MilestoneRepository(db)
    milestone = Milestone(**data.model_dump())
    return await repo.create(milestone)


@router.get("/{milestone_id}", response_model=MilestoneRead)
async def get_milestone(
    milestone_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    return await _milestone_in_workspace(db, milestone_id, ctx)


@router.put("/{milestone_id}", response_model=MilestoneRead)
async def update_milestone(
    milestone_id: UUID,
    data: MilestoneUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    milestone = await _milestone_in_workspace(db, milestone_id, ctx)
    if data.project_id is not None:
        await _project_in_workspace(db, data.project_id, ctx)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(milestone, field, value)
    await db.commit()
    await db.refresh(milestone)
    return milestone


@router.delete("/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_milestone(
    milestone_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    milestone = await _milestone_in_workspace(db, milestone_id, ctx)
    await MilestoneRepository(db).delete(milestone)
    return None
