from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.models.project import Project, ProjectStatus
from app.models.tag import Tag
from app.repositories.base_repo import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Project)

    async def search(
        self,
        q: str | None = None,
        status: ProjectStatus | None = None,
        owner: str | None = None,
        tag: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Project], int]:
        stmt = self._base_query()
        count_stmt = select(func.count()).select_from(Project).where(Project.deleted_at.is_(None))

        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Project.name).like(like),
                    func.lower(Project.description).like(like),
                )
            )
            count_stmt = count_stmt.where(
                or_(
                    func.lower(Project.name).like(like),
                    func.lower(Project.description).like(like),
                )
            )
        if status is not None:
            stmt = stmt.where(Project.status == status)
            count_stmt = count_stmt.where(Project.status == status)
        if owner:
            stmt = stmt.where(Project.owner == owner)
            count_stmt = count_stmt.where(Project.owner == owner)
        if tag:
            stmt = stmt.join(Project.tags).where(Tag.name == tag)
            count_stmt = count_stmt.join(Project.tags).where(Tag.name == tag)

        stmt = stmt.order_by(Project.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        items = list(result.scalars().unique().all())
        total = (await self.db.execute(count_stmt)).scalar() or 0
        return items, total

    async def get_by_id_with_tasks_and_milestones(self, project_id: UUID) -> Project | None:
        # selectin relationships already populate tasks/milestones on access.
        return await self.get_by_id(project_id)
