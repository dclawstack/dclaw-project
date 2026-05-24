from __future__ import annotations
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class MilestoneBase(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    target_date: date
    completed: bool = False


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneUpdate(BaseModel):
    project_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    target_date: date | None = None
    completed: bool | None = None


class MilestoneRead(MilestoneBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
