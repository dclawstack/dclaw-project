import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Awaitable, Callable

import structlog
from fastapi import Request, Response

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def _inject_request_id(_logger, _name, event_dict):
    event_dict.setdefault("request_id", request_id_ctx.get())
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    """Idempotent logging setup using structlog over the stdlib root logger."""
    logging.basicConfig(
        format="%(message)s", stream=sys.stdout, level=getattr(logging, level, logging.INFO)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _inject_request_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level, logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name) if name else structlog.get_logger()


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    incoming = request.headers.get("x-request-id")
    rid = incoming or uuid.uuid4().hex
    token = request_id_ctx.set(rid)
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response
    except Exception:
        # Re-raise so Starlette's exception middleware can build the 500,
        # but log the request-id first so the failing request is
        # correlatable. The synthesized error response won't carry the
        # header (we never own that object), so the log line is the
        # primary correlation surface.
        from app.core.logging import get_logger as _get_logger  # avoid cycle

        _get_logger("dclaw.request").error(
            "request.unhandled_exception",
            method=request.method,
            path=request.url.path,
            request_id=rid,
        )
        raise
    finally:
        request_id_ctx.reset(token)
