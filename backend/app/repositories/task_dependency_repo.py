from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.task_dependency import TaskDependency
from app.repositories.base_repo import BaseRepository


class TaskDependencyRepository(BaseRepository[TaskDependency]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, TaskDependency)

    async def list_for_project(self, project_id: UUID) -> list[TaskDependency]:
        """Return dependencies where either side is a task in this project.
        For CPM we want only edges where both ends are in the project, so we
        filter again at the service layer.
        """
        from app.models.task import Task

        result = await self.db.execute(
            select(TaskDependency)
            .join(Task, Task.id == TaskDependency.task_id)
            .where(Task.project_id == project_id, Task.deleted_at.is_(None))
        )
        return list(result.scalars().unique().all())

    async def list_for_task(self, task_id: UUID) -> list[TaskDependency]:
        result = await self.db.execute(
            select(TaskDependency).where(
                or_(
                    TaskDependency.task_id == task_id,
                    TaskDependency.depends_on_task_id == task_id,
                )
            )
        )
        return list(result.scalars().unique().all())
