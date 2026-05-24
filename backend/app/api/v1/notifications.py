import asyncio
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.core.database import get_db
from app.core.deps import AuthContext, require_workspace
from app.core.security import decode_token
from app.models.notification import Notification, NotificationKind
from app.repositories.user_repo import UserRepository
from app.repositories.workspace_repo import WorkspaceMemberRepository
from app.services.event_bus import get_event_bus

router = APIRouter()
events_router = APIRouter()


class NotificationRead(BaseModel):
    id: UUID
    workspace_id: UUID
    user_id: UUID
    kind: NotificationKind
    title: str
    body: str
    payload: dict
    read_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: List[NotificationRead]
    total: int
    unread: int


class MarkReadRequest(BaseModel):
    ids: List[UUID] | None = None  # None = mark all in workspace as read


async def _list_notifications_for(
    db: AsyncSession,
    ctx: AuthContext,
    *,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> NotificationListResponse:
    base = select(Notification).where(
        Notification.user_id == ctx.user.id,
        Notification.workspace_id == ctx.workspace.id,
    )
    if unread_only:
        base = base.where(Notification.read_at.is_(None))
    base = base.order_by(Notification.created_at.desc())
    rows = await db.execute(base.limit(limit).offset(offset))
    items = list(rows.scalars().all())

    total = (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == ctx.user.id,
                Notification.workspace_id == ctx.workspace.id,
            )
        )
    ).scalar() or 0
    unread = (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == ctx.user.id,
                Notification.workspace_id == ctx.workspace.id,
                Notification.read_at.is_(None),
            )
        )
    ).scalar() or 0
    return NotificationListResponse(items=items, total=total, unread=unread)


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    return await _list_notifications_for(
        db, ctx, unread_only=unread_only, limit=limit, offset=offset
    )


@router.post("/mark-read", response_model=NotificationListResponse)
async def mark_notifications_read(
    body: MarkReadRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    now = datetime.now(timezone.utc)
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == ctx.user.id,
            Notification.workspace_id == ctx.workspace.id,
            Notification.read_at.is_(None),
        )
        .values(read_at=now)
    )
    if body.ids:
        stmt = stmt.where(Notification.id.in_(body.ids))
    await db.execute(stmt)
    await db.commit()
    return await _list_notifications_for(db, ctx)


# ---- SSE stream -----------------------------------------------------------


async def _auth_from_query(
    db: AsyncSession, request: Request
) -> AuthContext:
    """SSE clients can't easily send custom headers from `EventSource`, so
    we also accept the JWT via a `?token=...` query param. The auth
    contract is identical to require_workspace; we just unwrap the token
    from a different place."""
    token = request.query_params.get("token") or ""
    if not token:
        # Fall back to header for non-browser clients.
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            token = header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        user_id = UUID(payload["sub"])
        workspace_id = UUID(payload["ws"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Token missing claims")

    user = await UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Unknown user")
    from app.repositories.workspace_repo import WorkspaceRepository

    workspace = await WorkspaceRepository(db).get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=403, detail="Unknown workspace")
    member = await WorkspaceMemberRepository(db).get_membership(workspace_id, user_id)
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    return AuthContext(user=user, workspace=workspace, membership=member)


@events_router.get("/stream", summary="SSE stream of workspace events")
async def event_stream(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ctx = await _auth_from_query(db, request)
    bus = get_event_bus()
    sub = await bus.subscribe(ctx.workspace.id)

    async def gen():
        try:
            # Initial comment line so proxies don't close the connection
            # before the first real event arrives.
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(sub.queue.get(), timeout=15.0)
                    yield event.as_sse()
                except asyncio.TimeoutError:
                    # Heartbeat keeps proxies + load balancers happy.
                    yield ": keep-alive\n\n"
        finally:
            await bus.unsubscribe(sub)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
