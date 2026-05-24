from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.milestone import Milestone
from app.repositories.base_repo import BaseRepository


class MilestoneRepository(BaseRepository[Milestone]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Milestone)

    async def list_by_project(
        self, project_id: UUID, limit: int = 20, offset: int = 0
    ) -> tuple[list[Milestone], int]:
        stmt = (
            select(Milestone)
            .where(Milestone.project_id == project_id, Milestone.deleted_at.is_(None))
            .order_by(Milestone.target_date.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.db.execute(
            select(func.count()).where(
                Milestone.project_id == project_id, Milestone.deleted_at.is_(None)
            )
        )
        total = count_result.scalar() or 0
        return items, total

    async def project_milestone_stats(self, project_id: UUID) -> tuple[int, int]:
        total = (
            await self.db.execute(
                select(func.count()).where(
                    Milestone.project_id == project_id, Milestone.deleted_at.is_(None)
                )
            )
        ).scalar() or 0
        completed = (
            await self.db.execute(
                select(func.count()).where(
                    Milestone.project_id == project_id,
                    Milestone.deleted_at.is_(None),
                    Milestone.completed.is_(True),
                )
            )
        ).scalar() or 0
        return total, completed
