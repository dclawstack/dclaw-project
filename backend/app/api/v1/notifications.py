import asyncio
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.core.database import get_db
from app.core.deps import AuthContext, require_workspace
from app.core.security import create_access_token, decode_token
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


# Short-lived stream token: minted via POST /events/token (which uses the
# regular Bearer-auth header), then handed to `EventSource` as ?token=.
# This keeps the long-lived JWT out of URLs, server access logs, browser
# history, and Referer headers. The stream token TTL is intentionally
# small — long enough to open the connection, short enough that a leaked
# log line isn't useful.
STREAM_TOKEN_TTL_SECONDS = 60
STREAM_TOKEN_CLAIM = "stream"


class StreamTokenResponse(BaseModel):
    token: str
    expires_in: int


@events_router.post("/token", response_model=StreamTokenResponse)
async def mint_stream_token(ctx: AuthContext = Depends(require_workspace)):
    """Mint a short-lived token (60s) for the SSE stream.

    Frontend flow: POST here with the long-lived Bearer JWT, get back a
    one-minute stream token, then open `EventSource('/stream?token=…')`
    with that. The stream token can only be used for /events/stream;
    other endpoints reject it because it lacks the regular claims.
    """
    payload_token = create_access_token(
        subject=str(ctx.user.id),
        extra_claims={
            "ws": str(ctx.workspace.id),
            STREAM_TOKEN_CLAIM: True,
        },
    )
    return StreamTokenResponse(
        token=payload_token, expires_in=STREAM_TOKEN_TTL_SECONDS
    )


async def _auth_from_query(
    db: AsyncSession, request: Request
) -> AuthContext:
    """Resolve the SSE caller from `?token=` (short-lived) or a Bearer header.

    The query-param token MUST carry the `stream` claim (minted by
    /events/token); a plain user JWT in `?token=` is rejected so we
    never normalize the anti-pattern of long-lived bearers in URLs.
    """
    token = request.query_params.get("token") or ""
    from_query = bool(token)
    if not from_query:
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            token = header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    if from_query and not payload.get(STREAM_TOKEN_CLAIM):
        # Refuse a regular Bearer JWT presented via the URL; the caller
        # must mint a stream token first.
        raise HTTPException(
            status_code=401,
            detail="Use POST /events/token to mint a stream token first.",
        )
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
                # Poll for disconnect at most 2s late so a dead client
                # doesn't hold a subscription open for the full 15s
                # heartbeat window (per code-review finding D-5).
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(sub.queue.get(), timeout=2.0)
                    yield event.as_sse()
                except asyncio.TimeoutError:
                    # Heartbeat every ~15s (every ~7 poll cycles).
                    if not hasattr(gen, "_ticks"):
                        gen._ticks = 0  # type: ignore[attr-defined]
                    gen._ticks = (getattr(gen, "_ticks", 0) + 1) % 7  # type: ignore[attr-defined]
                    if gen._ticks == 0:  # type: ignore[attr-defined]
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
