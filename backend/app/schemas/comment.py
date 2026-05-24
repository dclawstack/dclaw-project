from __future__ import annotations
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommentBase(BaseModel):
    author: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)


class CommentCreate(CommentBase):
    pass


class CommentUpdate(BaseModel):
    body: str | None = Field(default=None, min_length=1)


class CommentRead(CommentBase):
    id: uuid.UUID
    task_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
