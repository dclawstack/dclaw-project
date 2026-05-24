from __future__ import annotations
import uuid
from datetime import date, datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from app.models.project import ProjectStatus
from app.schemas.task import TaskRead
from app.schemas.milestone import MilestoneRead
from app.schemas.tag import TagRead


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: ProjectStatus = ProjectStatus.planning
    start_date: date | None = None
    end_date: date | None = None
    owner: str = Field(min_length=1, max_length=255)


class ProjectCreate(ProjectBase):
    tag_ids: List[uuid.UUID] = []


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    owner: str | None = Field(default=None, min_length=1, max_length=255)
    tag_ids: List[uuid.UUID] | None = None


class ProjectRead(ProjectBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    tags: List[TagRead] = []

    model_config = ConfigDict(from_attributes=True)


class ProjectDetailRead(ProjectRead):
    tasks: List[TaskRead] = []
    milestones: List[MilestoneRead] = []

    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseModel):
    items: List[ProjectRead]
    total: int
    limit: int
    offset: int


class ProjectStatsResponse(BaseModel):
    total_tasks: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    completion_pct: float
    overdue: int
    due_soon: int
    milestone_count: int
    milestone_completed: int
