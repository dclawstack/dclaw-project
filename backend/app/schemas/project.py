from __future__ import annotations
import uuid
from datetime import date
from typing import List

from pydantic import BaseModel, ConfigDict

from app.models.project import ProjectStatus
from app.schemas.task import TaskRead
from app.schemas.milestone import MilestoneRead


class ProjectBase(BaseModel):
    name: str
    description: str | None = None
    status: ProjectStatus = ProjectStatus.planning
    start_date: date | None = None
    end_date: date | None = None
    owner: str


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    owner: str | None = None


class ProjectRead(ProjectBase):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class ProjectDetailRead(ProjectRead):
    tasks: List[TaskRead] = []
    milestones: List[MilestoneRead] = []

    model_config = ConfigDict(from_attributes=True)
