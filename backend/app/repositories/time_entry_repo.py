from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.time_entry import TimeEntry
from app.repositories.base_repo import BaseRepository


class TimeEntryRepository(BaseRepository[TimeEntry]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, TimeEntry)

    async def active_for_user(self, user_id: UUID) -> TimeEntry | None:
        result = await self.db.execute(
            select(TimeEntry).where(
                TimeEntry.user_id == user_id, TimeEntry.ended_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def list_for_task(self, task_id: UUID) -> list[TimeEntry]:
        result = await self.db.execute(
            select(TimeEntry)
            .where(TimeEntry.task_id == task_id)
            .order_by(TimeEntry.started_at.desc())
        )
        return list(result.scalars().all())

    async def summary_for_task(self, task_id: UUID) -> tuple[int, int, int]:
        stmt = select(
            func.coalesce(func.sum(TimeEntry.duration_seconds), 0),
            func.coalesce(
                func.sum(
                    func.coalesce(TimeEntry.duration_seconds, 0)
                ).filter(TimeEntry.billable.is_(True)),
                0,
            ),
            func.count(),
        ).where(TimeEntry.task_id == task_id)
        result = await self.db.execute(stmt)
        total, billable, entries = result.one()
        return int(total), int(billable), int(entries)
