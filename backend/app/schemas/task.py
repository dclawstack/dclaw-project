from __future__ import annotations
import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.task import TaskStatus, TaskPriority


class TaskBase(BaseModel):
    project_id: uuid.UUID
    title: str
    description: str | None = None
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    assignee: str | None = None
    due_date: date | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    project_id: uuid.UUID | None = None
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee: str | None = None
    due_date: date | None = None


class TaskRead(TaskBase):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
