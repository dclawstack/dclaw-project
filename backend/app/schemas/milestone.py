from __future__ import annotations
import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class MilestoneBase(BaseModel):
    project_id: uuid.UUID
    name: str
    description: str | None = None
    target_date: date
    completed: bool = False


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneUpdate(BaseModel):
    project_id: uuid.UUID | None = None
    name: str | None = None
    description: str | None = None
    target_date: date | None = None
    completed: bool | None = None


class MilestoneRead(MilestoneBase):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
