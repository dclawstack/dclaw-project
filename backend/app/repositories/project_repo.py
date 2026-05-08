from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.project import Project
from app.repositories.base_repo import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Project)

    async def get_by_id_with_tasks_and_milestones(self, project_id: UUID) -> Project | None:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()
