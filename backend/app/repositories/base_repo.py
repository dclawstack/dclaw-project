from uuid import UUID
from datetime import datetime, timezone
from typing import TypeVar, Generic

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.base import Base
from app.models.mixins import SoftDeleteMixin

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Generic async CRUD repository.

    Soft-delete aware: if the model inherits SoftDeleteMixin, list_all and
    get_by_id filter out tombstoned rows by default.
    """

    def __init__(self, db: AsyncSession, model: type[T]):
        self.db = db
        self.model = model

    @property
    def _is_soft_delete(self) -> bool:
        return issubclass(self.model, SoftDeleteMixin)

    def _base_query(self):
        stmt = select(self.model)
        if self._is_soft_delete:
            stmt = stmt.where(self.model.deleted_at.is_(None))
        return stmt

    async def list_all(self, limit: int = 20, offset: int = 0) -> tuple[list[T], int]:
        stmt = self._base_query().limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        count_stmt = select(func.count()).select_from(self.model)
        if self._is_soft_delete:
            count_stmt = count_stmt.where(self.model.deleted_at.is_(None))
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0
        return items, total

    async def get_by_id(self, item_id: UUID) -> T | None:
        stmt = self._base_query().where(self.model.id == item_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, obj: T) -> T:
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: T) -> None:
        """Soft-delete when supported, hard-delete otherwise."""
        if self._is_soft_delete:
            obj.deleted_at = datetime.now(timezone.utc)
            await self.db.commit()
        else:
            await self.db.delete(obj)
            await self.db.commit()

    async def hard_delete(self, obj: T) -> None:
        await self.db.delete(obj)
        await self.db.commit()

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        if self._is_soft_delete:
            stmt = stmt.where(self.model.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar() or 0
