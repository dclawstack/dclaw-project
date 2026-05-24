"""Auth + workspace dependency-injection helpers.

The contract every protected route inherits from `require_workspace`:
- Caller MUST present `Authorization: Bearer <jwt>`.
- The JWT MUST encode a `sub` (user id) and a `ws` (active workspace id).
- The user MUST be a member of the workspace; otherwise 403.

`require_workspace_role` adds a minimum-role check on top.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.repositories.user_repo import UserRepository
from app.repositories.workspace_repo import (
    WorkspaceMemberRepository,
    WorkspaceRepository,
)


_ROLE_PRIORITY = {
    WorkspaceRole.viewer: 0,
    WorkspaceRole.member: 1,
    WorkspaceRole.admin: 2,
    WorkspaceRole.owner: 3,
}


@dataclass
class AuthContext:
    user: User
    workspace: Workspace
    membership: WorkspaceMember


def _extract_bearer(request: Request) -> str:
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return header.split(" ", 1)[1].strip()


async def require_workspace(
    request: Request, db: AsyncSession = Depends(get_db)
) -> AuthContext:
    token = _extract_bearer(request)
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    try:
        user_id = UUID(payload["sub"])
        workspace_id = UUID(payload["ws"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims",
        )

    user = await UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")

    workspace = await WorkspaceRepository(db).get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown workspace")

    member = await WorkspaceMemberRepository(db).get_membership(workspace_id, user_id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this workspace",
        )
    return AuthContext(user=user, workspace=workspace, membership=member)


def require_workspace_role(min_role: WorkspaceRole):
    """Dependency factory: require at least the given role in the active workspace."""
    threshold = _ROLE_PRIORITY[min_role]

    async def _checker(ctx: AuthContext = Depends(require_workspace)) -> AuthContext:
        if _ROLE_PRIORITY[ctx.membership.role] < threshold:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role {min_role.value} or higher",
            )
        return ctx

    return _checker


CurrentUser = Annotated[AuthContext, Depends(require_workspace)]
