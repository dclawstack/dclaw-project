from __future__ import annotations
import uuid
from datetime import date, datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskStatus, TaskPriority
from app.schemas.tag import TagRead


class TaskBase(BaseModel):
    project_id: uuid.UUID
    parent_task_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    assignee: str | None = Field(default=None, max_length=255)
    due_date: date | None = None
    estimated_hours: int | None = Field(default=None, ge=0, le=10000)


class TaskCreate(TaskBase):
    tag_ids: List[uuid.UUID] = []


class TaskUpdate(BaseModel):
    project_id: uuid.UUID | None = None
    parent_task_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee: str | None = Field(default=None, max_length=255)
    due_date: date | None = None
    estimated_hours: int | None = Field(default=None, ge=0, le=10000)
    tag_ids: List[uuid.UUID] | None = None


class TaskRead(TaskBase):
    id: uuid.UUID
    completed_at: date | None = None
    created_at: datetime
    updated_at: datetime
    tags: List[TagRead] = []

    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    items: List[TaskRead]
    total: int
    limit: int
    offset: int


class TaskBulkPatch(BaseModel):
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee: str | None = None


class TaskBulkRequest(BaseModel):
    ids: List[uuid.UUID] = Field(min_length=1)
    patch: TaskBulkPatch
