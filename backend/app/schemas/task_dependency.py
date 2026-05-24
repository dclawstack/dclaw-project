from __future__ import annotations
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.task_dependency import DependencyType


class TaskDependencyCreate(BaseModel):
    depends_on_task_id: uuid.UUID
    type: DependencyType = DependencyType.FS


class TaskDependencyRead(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    depends_on_task_id: uuid.UUID
    type: DependencyType
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduledTaskRead(BaseModel):
    task_id: uuid.UUID
    title: str
    duration_days: int
    earliest_start: int
    earliest_finish: int
    latest_start: int
    latest_finish: int
    slack: int
    is_critical: bool


class CriticalPathRead(BaseModel):
    project_id: uuid.UUID
    total_duration_days: int
    critical_chain: list[uuid.UUID]
    schedule: list[ScheduledTaskRead]
    cycles_detected: bool = False
