"""Local stubs for external integrations.

Each integration ships behind a small abstract surface so the real
provider can be slotted in later by registering a different class with
the registry. Today every adapter is a NO-OP that records the intent
and returns a 200-shape response — enough for the UI to wire up and for
contracts to be testable without touching a live service.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

log = get_logger("dclaw.integrations")


# ---- Stripe (6.6) ---------------------------------------------------------


@dataclass
class UsageEvent:
    id: str
    workspace_id: str
    metric: str
    quantity: int
    ts: float


class StripeStub:
    """Records would-be Stripe API calls in memory.

    Replace `StripeStub` with `stripe.Stripe(api_key=...)` to talk to the
    real API. The interface (record_usage, create_portal_session) is the
    contract callers should depend on.
    """

    def __init__(self) -> None:
        self.usage: list[UsageEvent] = []
        self.subscriptions: dict[str, dict] = {}

    def record_usage(self, *, workspace_id: str, metric: str, quantity: int) -> UsageEvent:
        event = UsageEvent(
            id=uuid.uuid4().hex,
            workspace_id=workspace_id,
            metric=metric,
            quantity=quantity,
            ts=time.time(),
        )
        self.usage.append(event)
        log.info("stripe.usage_recorded", **event.__dict__)
        return event

    def create_portal_session(self, workspace_id: str) -> dict:
        return {
            "id": uuid.uuid4().hex,
            "workspace_id": workspace_id,
            "url": f"https://billing-portal.local/stub/{workspace_id}",
            "stub": True,
        }

    def get_usage(self, workspace_id: str) -> list[UsageEvent]:
        return [u for u in self.usage if u.workspace_id == workspace_id]


# ---- Slack (6.7) ----------------------------------------------------------


@dataclass
class SlackMessage:
    workspace_id: str
    channel: str
    text: str
    ts: float = field(default_factory=time.time)


class SlackStub:
    def __init__(self) -> None:
        self.outbox: list[SlackMessage] = []

    def post_message(self, *, workspace_id: str, channel: str, text: str) -> SlackMessage:
        msg = SlackMessage(workspace_id=workspace_id, channel=channel, text=text)
        self.outbox.append(msg)
        log.info(
            "slack.post_message", workspace_id=workspace_id, channel=channel, text=text[:200]
        )
        return msg


# ---- GitHub (6.7) ---------------------------------------------------------


@dataclass
class GitHubIssue:
    workspace_id: str
    repo: str
    title: str
    body: str
    number: int


class GitHubStub:
    def __init__(self) -> None:
        self._counter: dict[str, int] = {}
        self.issues: list[GitHubIssue] = []

    def open_issue(self, *, workspace_id: str, repo: str, title: str, body: str) -> GitHubIssue:
        n = self._counter.get(repo, 0) + 1
        self._counter[repo] = n
        issue = GitHubIssue(
            workspace_id=workspace_id, repo=repo, title=title, body=body, number=n
        )
        self.issues.append(issue)
        log.info("github.open_issue", workspace_id=workspace_id, repo=repo, number=n)
        return issue

    def list_issues(self, workspace_id: str) -> list[GitHubIssue]:
        return [i for i in self.issues if i.workspace_id == workspace_id]


# ---- Logto OAuth (6.8) ----------------------------------------------------


@dataclass
class LogtoUser:
    sub: str
    email: str
    name: str


class LogtoStub:
    """Pretends to be a Logto JWKS validator.

    The real implementation downloads the workspace's JWKS, verifies
    signature + iss/aud claims, and returns the resolved user. The stub
    accepts any token whose `sub` claim looks like an email-shaped
    string — enough to wire UI components and integration tests.
    """

    def validate(self, token: str) -> LogtoUser | None:
        # Accept "stub.<email>" tokens for testing convenience.
        if not token.startswith("stub."):
            return None
        email = token[len("stub.") :]
        if "@" not in email:
            return None
        return LogtoUser(sub=email, email=email, name=email.split("@")[0].title())


# ---- Registry -------------------------------------------------------------


_singletons: dict[str, Any] = {}


def get_stripe() -> StripeStub:
    return _singletons.setdefault("stripe", StripeStub())


def get_slack() -> SlackStub:
    return _singletons.setdefault("slack", SlackStub())


def get_github() -> GitHubStub:
    return _singletons.setdefault("github", GitHubStub())


def get_logto() -> LogtoStub:
    return _singletons.setdefault("logto", LogtoStub())


def reset_integrations() -> None:
    """Test helper — wipe all stub state between tests."""
    _singletons.clear()
