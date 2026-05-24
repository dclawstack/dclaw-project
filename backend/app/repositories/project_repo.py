from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.models.project import Project, ProjectStatus
from app.models.tag import Tag
from app.repositories.base_repo import BaseRepository, escape_like, LIKE_ESCAPE


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Project)

    async def search(
        self,
        workspace_id: UUID,
        q: str | None = None,
        status: ProjectStatus | None = None,
        owner: str | None = None,
        tag: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Project], int]:
        stmt = self._base_query().where(Project.workspace_id == workspace_id)
        # DISTINCT count prevents many-to-many JOINs (tag filter) from
        # inflating `total` past the number of unique projects.
        count_stmt = (
            select(func.count(func.distinct(Project.id)))
            .select_from(Project)
            .where(
                Project.deleted_at.is_(None),
                Project.workspace_id == workspace_id,
            )
        )

        if q:
            like = f"%{escape_like(q.lower())}%"
            text_match = or_(
                func.lower(Project.name).like(like, escape=LIKE_ESCAPE),
                func.lower(Project.description).like(like, escape=LIKE_ESCAPE),
            )
            stmt = stmt.where(text_match)
            count_stmt = count_stmt.where(text_match)
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

    async def get_by_id_in_workspace(
        self, project_id: UUID, workspace_id: UUID
    ) -> Project | None:
        result = await self.db.execute(
            self._base_query().where(
                Project.id == project_id, Project.workspace_id == workspace_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_tasks_and_milestones(self, project_id: UUID) -> Project | None:
        # selectin relationships already populate tasks/milestones on access.
        return await self.get_by_id(project_id)
