from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy import func

from app.models.milestone import Milestone
from app.repositories.base_repo import BaseRepository


class MilestoneRepository(BaseRepository[Milestone]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Milestone)

    async def list_by_project(self, project_id: UUID, limit: int = 20, offset: int = 0) -> tuple[list[Milestone], int]:
        result = await self.db.execute(
            select(Milestone).where(Milestone.project_id == project_id).limit(limit).offset(offset)
        )
        items = list(result.scalars().all())
        count_result = await self.db.execute(
            select(func.count()).where(Milestone.project_id == project_id)
        )
        total = count_result.scalar() or 0
        return items, total
