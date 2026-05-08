from uuid import UUID
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.task import Task, TaskStatus
from app.repositories.base_repo import BaseRepository


class TaskRepository(BaseRepository[Task]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Task)

    async def list_by_project(self, project_id: UUID, limit: int = 20, offset: int = 0) -> tuple[list[Task], int]:
        result = await self.db.execute(
            select(Task).where(Task.project_id == project_id).limit(limit).offset(offset)
        )
        items = list(result.scalars().all())
        from sqlalchemy import func
        count_result = await self.db.execute(
            select(func.count()).where(Task.project_id == project_id)
        )
        total = count_result.scalar() or 0
        return items, total

    async def list_due_today(self, today: date) -> list[Task]:
        result = await self.db.execute(
            select(Task).where(
                and_(Task.due_date == today, Task.status != TaskStatus.done)
            )
        )
        return list(result.scalars().all())

    async def list_overdue(self, today: date) -> list[Task]:
        result = await self.db.execute(
            select(Task).where(
                and_(Task.due_date < today, Task.status != TaskStatus.done)
            )
        )
        return list(result.scalars().all())

    async def count_by_status(self, status: TaskStatus) -> int:
        from sqlalchemy import func
        result = await self.db.execute(
            select(func.count()).where(Task.status == status)
        )
        return result.scalar() or 0
