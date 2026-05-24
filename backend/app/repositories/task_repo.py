from uuid import UUID
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_

from app.models.task import Task, TaskStatus, TaskPriority
from app.models.tag import Tag
from app.repositories.base_repo import BaseRepository


class TaskRepository(BaseRepository[Task]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Task)

    async def search(
        self,
        project_id: UUID | None = None,
        parent_task_id: UUID | None = None,
        q: str | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee: str | None = None,
        tag: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Task], int]:
        stmt = self._base_query()
        count_stmt = select(func.count()).select_from(Task).where(Task.deleted_at.is_(None))

        if project_id is not None:
            stmt = stmt.where(Task.project_id == project_id)
            count_stmt = count_stmt.where(Task.project_id == project_id)
        if parent_task_id is not None:
            stmt = stmt.where(Task.parent_task_id == parent_task_id)
            count_stmt = count_stmt.where(Task.parent_task_id == parent_task_id)
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Task.title).like(like),
                    func.lower(Task.description).like(like),
                )
            )
            count_stmt = count_stmt.where(
                or_(
                    func.lower(Task.title).like(like),
                    func.lower(Task.description).like(like),
                )
            )
        if status is not None:
            stmt = stmt.where(Task.status == status)
            count_stmt = count_stmt.where(Task.status == status)
        if priority is not None:
            stmt = stmt.where(Task.priority == priority)
            count_stmt = count_stmt.where(Task.priority == priority)
        if assignee:
            stmt = stmt.where(Task.assignee == assignee)
            count_stmt = count_stmt.where(Task.assignee == assignee)
        if tag:
            stmt = stmt.join(Task.tags).where(Tag.name == tag)
            count_stmt = count_stmt.join(Task.tags).where(Tag.name == tag)

        stmt = stmt.order_by(Task.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        items = list(result.scalars().unique().all())
        total = (await self.db.execute(count_stmt)).scalar() or 0
        return items, total

    async def list_by_project(
        self, project_id: UUID, limit: int = 20, offset: int = 0
    ) -> tuple[list[Task], int]:
        return await self.search(project_id=project_id, limit=limit, offset=offset)

    async def list_due_today(self, today: date) -> list[Task]:
        result = await self.db.execute(
            select(Task).where(
                and_(
                    Task.due_date == today,
                    Task.status != TaskStatus.done,
                    Task.deleted_at.is_(None),
                )
            )
        )
        return list(result.scalars().all())

    async def list_overdue(self, today: date) -> list[Task]:
        result = await self.db.execute(
            select(Task).where(
                and_(
                    Task.due_date < today,
                    Task.status != TaskStatus.done,
                    Task.deleted_at.is_(None),
                )
            )
        )
        return list(result.scalars().all())

    async def list_due_within(self, start: date, end: date) -> list[Task]:
        result = await self.db.execute(
            select(Task).where(
                and_(
                    Task.due_date >= start,
                    Task.due_date <= end,
                    Task.status != TaskStatus.done,
                    Task.deleted_at.is_(None),
                )
            )
        )
        return list(result.scalars().all())

    async def count_by_status(self, status: TaskStatus) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                and_(Task.status == status, Task.deleted_at.is_(None))
            )
        )
        return result.scalar() or 0

    async def get_many(self, ids: list[UUID]) -> list[Task]:
        if not ids:
            return []
        result = await self.db.execute(
            select(Task).where(
                and_(Task.id.in_(ids), Task.deleted_at.is_(None))
            )
        )
        return list(result.scalars().all())

    async def project_stats(self, project_id: UUID) -> dict:
        """Aggregate task stats for a project."""
        base = and_(Task.project_id == project_id, Task.deleted_at.is_(None))
        result = await self.db.execute(
            select(Task.status, func.count()).where(base).group_by(Task.status)
        )
        by_status: dict[str, int] = {s.value: 0 for s in TaskStatus}
        for status, count in result.all():
            by_status[status.value] = count

        result = await self.db.execute(
            select(Task.priority, func.count()).where(base).group_by(Task.priority)
        )
        by_priority: dict[str, int] = {p.value: 0 for p in TaskPriority}
        for priority, count in result.all():
            by_priority[priority.value] = count

        total = sum(by_status.values())
        completed = by_status.get(TaskStatus.done.value, 0)
        completion_pct = (completed / total * 100) if total else 0.0

        from datetime import date as _date

        today = _date.today()
        overdue = (
            await self.db.execute(
                select(func.count()).where(
                    and_(base, Task.due_date < today, Task.status != TaskStatus.done)
                )
            )
        ).scalar() or 0
        due_soon = (
            await self.db.execute(
                select(func.count()).where(
                    and_(
                        base,
                        Task.due_date >= today,
                        Task.due_date <= _date.fromordinal(today.toordinal() + 7),
                        Task.status != TaskStatus.done,
                    )
                )
            )
        ).scalar() or 0

        return {
            "total_tasks": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "completion_pct": round(completion_pct, 2),
            "overdue": overdue,
            "due_soon": due_soon,
        }
