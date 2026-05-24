"""In-process event bus + SSE-ready async pub/sub.

YC-grade real-time without dragging in Redis/NATS yet. Subscribers (one
per active SSE connection) get a per-workspace `asyncio.Queue`; emitters
publish to all subscribers of the relevant workspace. Bounded queues drop
the oldest event on overflow so a slow client can't OOM the server.

Loop affinity note: `asyncio.Queue` is bound to whichever event loop is
running when it's instantiated. We create the queue lazily inside
`subscribe()` so each SSE handler (running on its own request loop)
gets a queue bound to that loop. The bus itself stores no asyncio
primitives — only plain dict/list — which keeps it safe across the
per-test loops that pytest-asyncio creates.

Swap-out: replace `EventBus` with a Redis-backed Pub/Sub in production.
The emit/subscribe API stays the same.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator
from uuid import UUID, uuid4


@dataclass
class Event:
    id: str
    kind: str
    workspace_id: str
    payload: dict
    ts: str

    def as_sse(self) -> str:
        """Serialize to the wire format defined by the SSE spec."""
        return (
            f"id: {self.id}\n"
            f"event: {self.kind}\n"
            f"data: {json.dumps(asdict(self))}\n\n"
        )


@dataclass
class _Subscription:
    workspace_id: str
    queue: asyncio.Queue
    id: str = field(default_factory=lambda: uuid4().hex)


class EventBus:
    """Per-workspace fan-out via asyncio.Queue.

    Bounded queues: oldest event is dropped on full so a slow consumer
    can never grow memory without bound. No asyncio primitives are
    stored on the bus itself; queues are created lazily by callers
    inside their own event loops to avoid cross-loop binding issues.
    """

    def __init__(self, *, queue_size: int = 100):
        self._subs: dict[str, list[_Subscription]] = {}
        self._queue_size = queue_size

    async def subscribe(self, workspace_id: UUID | str) -> _Subscription:
        wsid = str(workspace_id)
        # Queue is created in the caller's running loop on purpose.
        sub = _Subscription(
            workspace_id=wsid, queue=asyncio.Queue(maxsize=self._queue_size)
        )
        self._subs.setdefault(wsid, []).append(sub)
        return sub

    async def unsubscribe(self, sub: _Subscription) -> None:
        bucket = self._subs.get(sub.workspace_id, [])
        self._subs[sub.workspace_id] = [s for s in bucket if s.id != sub.id]

    def publish(
        self, *, workspace_id: UUID | str, kind: str, payload: dict
    ) -> None:
        """Non-blocking publish. Safe to call from inside request handlers.

        Any per-subscriber failure (queue bound to a foreign loop, slow
        consumer eviction, etc.) is swallowed so publishing never breaks
        the originating request.
        """
        wsid = str(workspace_id)
        event = Event(
            id=uuid4().hex,
            kind=kind,
            workspace_id=wsid,
            payload=payload,
            ts=datetime.now(timezone.utc).isoformat(),
        )
        for sub in list(self._subs.get(wsid, [])):
            self._safe_enqueue(sub, event)

    def _safe_enqueue(self, sub: _Subscription, event: Event) -> None:
        try:
            sub.queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                sub.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                sub.queue.put_nowait(event)
            except (asyncio.QueueFull, RuntimeError):
                pass
        except RuntimeError:
            # Queue is bound to a different (closed) event loop — the
            # subscriber lives in a dead test; drop the subscription
            # so we don't keep hitting it.
            self._subs[sub.workspace_id] = [
                s for s in self._subs.get(sub.workspace_id, []) if s.id != sub.id
            ]

    async def stream(self, sub: _Subscription) -> AsyncIterator[Event]:
        """Yield events as they arrive on the subscription's queue."""
        while True:
            event = await sub.queue.get()
            yield event


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def reset_event_bus() -> None:
    """Drop the cached bus — used by tests that want a clean fixture."""
    global _bus
    _bus = None
