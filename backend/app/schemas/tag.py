from __future__ import annotations
import uuid

from pydantic import BaseModel, ConfigDict, Field


class TagBase(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str = Field(default="#64748b", max_length=16)


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=16)


class TagRead(TagBase):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
