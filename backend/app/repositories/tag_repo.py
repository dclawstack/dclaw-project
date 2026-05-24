from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tag import Tag
from app.repositories.base_repo import BaseRepository


class TagRepository(BaseRepository[Tag]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Tag)

    async def list_for_workspace(self, workspace_id: UUID) -> list[Tag]:
        result = await self.db.execute(
            select(Tag).where(Tag.workspace_id == workspace_id).order_by(Tag.name.asc())
        )
        return list(result.scalars().all())

    async def get_by_name_in_workspace(
        self, name: str, workspace_id: UUID
    ) -> Tag | None:
        result = await self.db.execute(
            select(Tag).where(Tag.name == name, Tag.workspace_id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def get_in_workspace(
        self, tag_id: UUID, workspace_id: UUID
    ) -> Tag | None:
        result = await self.db.execute(
            select(Tag).where(Tag.id == tag_id, Tag.workspace_id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def get_many(self, ids: list[UUID]) -> list[Tag]:
        """Used by project/task creation to attach tag objects by id.

        Callers are responsible for ensuring the ids come from a trusted
        UI flow that only surfaced tags in the active workspace.
        """
        if not ids:
            return []
        result = await self.db.execute(select(Tag).where(Tag.id.in_(ids)))
        return list(result.scalars().all())

    async def get_many_in_workspace(
        self, ids: list[UUID], workspace_id: UUID
    ) -> list[Tag]:
        """Like get_many but drops any id that isn't in the caller's
        workspace. Use this on the write path so cross-tenant tag-id
        guessing can't attach foreign tags to local entities."""
        if not ids:
            return []
        result = await self.db.execute(
            select(Tag).where(Tag.id.in_(ids), Tag.workspace_id == workspace_id)
        )
        return list(result.scalars().all())
