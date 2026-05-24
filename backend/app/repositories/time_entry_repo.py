from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.project import Project
from app.models.task import Task
from app.models.time_entry import TimeEntry
from app.repositories.base_repo import BaseRepository


class TimeEntryRepository(BaseRepository[TimeEntry]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, TimeEntry)

    async def active_for_user(
        self, user_id: UUID, workspace_id: UUID | None = None
    ) -> TimeEntry | None:
        """Return the user's running timer, scoped to a workspace by default.

        Without the workspace filter a user with timers in two workspaces
        would have their A-side timer silently stopped when they hit
        /start in workspace B. The .first() call also tolerates the race
        condition where a double-click leaves two open rows — we return
        the most recent one rather than crashing with MultipleResultsFound.
        """
        stmt = select(TimeEntry).where(TimeEntry.ended_at.is_(None))
        stmt = stmt.where(TimeEntry.user_id == user_id)
        if workspace_id is not None:
            stmt = stmt.join(Task, Task.id == TimeEntry.task_id).join(
                Project, Project.id == Task.project_id
            ).where(Project.workspace_id == workspace_id)
        stmt = stmt.order_by(TimeEntry.started_at.desc())
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_for_user_in_workspace(
        self, entry_id: UUID, user_id: UUID, workspace_id: UUID
    ) -> TimeEntry | None:
        """Defense-in-depth load: only returns the entry if it belongs to
        this user AND its task's project is in this workspace."""
        result = await self.db.execute(
            select(TimeEntry)
            .join(Task, Task.id == TimeEntry.task_id)
            .join(Project, Project.id == Task.project_id)
            .where(
                TimeEntry.id == entry_id,
                TimeEntry.user_id == user_id,
                Project.workspace_id == workspace_id,
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
