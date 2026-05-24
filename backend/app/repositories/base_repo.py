from uuid import UUID
from datetime import datetime, timezone
from typing import TypeVar, Generic

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.models.base import Base
from app.models.mixins import SoftDeleteMixin

T = TypeVar("T", bound=Base)


# Per-parent-model soft-delete cascade map. Each entry says "when row R of
# model M is tombstoned, also tombstone every live child whose FK column
# equals R.id, in each of these child tables." We use bulk UPDATE rather
# than walking the ORM relationship so we don't have to load the children
# into the session (which has surprising interactions with the
# self-referential `cascade="all, delete-orphan"` on Task.subtasks).
_SOFT_DELETE_CASCADE: dict[type, list[tuple[type, str]]] = {}


def register_soft_delete_cascade(
    parent_model: type, *child_specs: tuple[type, str]
) -> None:
    """Register `(ChildModel, fk_column_name)` pairs to cascade-soft-delete
    when a parent of `parent_model` is tombstoned."""
    _SOFT_DELETE_CASCADE[parent_model] = list(child_specs)


def escape_like(term: str) -> str:
    """Escape SQL LIKE metacharacters in user input.

    Without this, a user's `%` or `_` in a search query becomes a wildcard:
    `q=%` would match every row, and `q=a_b` would match `axb`. Returns a
    string suitable for embedding inside an outer `%...%` pattern; the
    caller must also pass `escape="\\"` to the LIKE clause so the DB
    interprets backslashes consistently across SQLite and Postgres.
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


LIKE_ESCAPE = "\\"


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
        """Soft-delete when supported, hard-delete otherwise.

        For soft-delete we also fire a bulk-UPDATE per registered child
        relationship so deleted parents don't leave orphans visible
        through global list queries.
        """
        if self._is_soft_delete:
            now = datetime.now(timezone.utc)
            for child_model, fk_attr in _SOFT_DELETE_CASCADE.get(type(obj), []):
                fk_col = getattr(child_model, fk_attr)
                await self.db.execute(
                    update(child_model)
                    .where(fk_col == obj.id, child_model.deleted_at.is_(None))
                    .values(deleted_at=now)
                )
            obj.deleted_at = now
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
