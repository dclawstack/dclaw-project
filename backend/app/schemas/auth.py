from __future__ import annotations
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=255)
    workspace_name: str | None = Field(
        default=None,
        max_length=255,
        description="If provided, a new workspace is created and the user is its owner.",
    )


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMembershipRead(BaseModel):
    workspace: WorkspaceRead
    role: str

    model_config = ConfigDict(from_attributes=True)


class AuthMe(BaseModel):
    user: UserRead
    workspaces: list[WorkspaceMembershipRead]
    active_workspace: WorkspaceRead


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
    workspace: WorkspaceRead


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
