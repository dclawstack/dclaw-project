from __future__ import annotations
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TimeEntryStart(BaseModel):
    task_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=500)
    billable: bool = True


class TimeEntryManual(BaseModel):
    task_id: uuid.UUID
    started_at: datetime
    ended_at: datetime
    notes: str | None = Field(default=None, max_length=500)
    billable: bool = True


class TimeEntryUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=500)
    billable: bool | None = None
    ended_at: datetime | None = None


class TimeEntryRead(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    billable: bool
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimeSummary(BaseModel):
    task_id: uuid.UUID
    total_seconds: int
    billable_seconds: int
    entries: int
