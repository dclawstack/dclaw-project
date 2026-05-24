"""Analytics endpoints (burndown, velocity, schedule data)."""
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthContext, require_workspace
from app.repositories.project_repo import ProjectRepository
from app.services.burndown import compute_burndown

router = APIRouter()


class BurndownPointRead(BaseModel):
    day: date
    remaining: int
    completed: int


class BurndownResponse(BaseModel):
    project_id: UUID
    start: date
    end: date
    total: int
    velocity_per_week: float
    points: list[BurndownPointRead]


async def _project_in_workspace(
    db: AsyncSession, project_id: UUID, ctx: AuthContext
):
    project = await ProjectRepository(db).get_by_id_in_workspace(
        project_id, ctx.workspace.id
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/burndown", response_model=BurndownResponse)
async def project_burndown(
    project_id: UUID,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    project = await _project_in_workspace(db, project_id, ctx)
    report = compute_burndown(project.active_tasks, start=start, end=end)
    return BurndownResponse(
        project_id=project_id,
        start=report.start,
        end=report.end,
        total=report.total,
        velocity_per_week=report.velocity_per_week,
        points=[
            BurndownPointRead(day=p.day, remaining=p.remaining, completed=p.completed)
            for p in report.points
        ],
    )
