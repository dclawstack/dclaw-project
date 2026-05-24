from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.repositories.base_repo import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Workspace)

    async def get_by_slug(self, slug: str) -> Workspace | None:
        result = await self.db.execute(select(Workspace).where(Workspace.slug == slug))
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: UUID) -> list[Workspace]:
        result = await self.db.execute(
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at.asc())
        )
        return list(result.scalars().unique().all())


class WorkspaceMemberRepository(BaseRepository[WorkspaceMember]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, WorkspaceMember)

    async def get_membership(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceMember | None:
        result = await self.db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
