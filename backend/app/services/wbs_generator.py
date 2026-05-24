"""AI-generated Work Breakdown Structure (WBS).

YC headline acceptance: "Generate a full WBS in <2 minutes." This service
produces a structured task tree from a natural-language goal, validates the
output, and persists it in a single transaction so the UI gets an instantly
usable project plan.

When no LLM is reachable, we ship a deterministic 5-phase template so the
demo path is always live.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.services.ai_copilot import AICopilotService, ChatMessage, get_copilot


WBS_SYSTEM_PROMPT = (
    "You are DClaw Copilot, an expert project planner. "
    "Given a project goal you produce a Work Breakdown Structure as JSON ONLY. "
    "Schema: {\"tasks\": [{\"title\": str, \"description\": str, \"priority\": "
    "\"low\"|\"medium\"|\"high\"|\"urgent\", \"estimated_hours\": int, "
    "\"depends_on\": [int]}], \"milestones\": [{\"name\": str, \"target_offset_days\": int}]}. "
    "Use depends_on with 0-based indices into the tasks array. "
    "Keep task titles short and verb-led. Return JSON only — no markdown."
)


@dataclass
class WBSRequest:
    goal: str
    deadline_days: int = 30
    team_size: int = 3


@dataclass
class GeneratedTask:
    title: str
    description: str
    priority: str
    estimated_hours: int
    depends_on: list[int]


@dataclass
class GeneratedMilestone:
    name: str
    target_offset_days: int


@dataclass
class WBSResult:
    tasks: list[GeneratedTask]
    milestones: list[GeneratedMilestone]
    provider: str
    model: str


FALLBACK_WBS = {
    "tasks": [
        {
            "title": "Discovery and requirements gathering",
            "description": "Interview stakeholders, define scope, lock acceptance criteria.",
            "priority": "high",
            "estimated_hours": 16,
            "depends_on": [],
        },
        {
            "title": "Solution design",
            "description": "Architecture diagram, data model, UX wireframes.",
            "priority": "high",
            "estimated_hours": 24,
            "depends_on": [0],
        },
        {
            "title": "Implement backend",
            "description": "Build API endpoints, schema, repositories, tests.",
            "priority": "high",
            "estimated_hours": 80,
            "depends_on": [1],
        },
        {
            "title": "Implement frontend",
            "description": "Build pages, components, and API integration.",
            "priority": "high",
            "estimated_hours": 60,
            "depends_on": [1],
        },
        {
            "title": "QA and hardening",
            "description": "End-to-end tests, performance pass, security review.",
            "priority": "medium",
            "estimated_hours": 32,
            "depends_on": [2, 3],
        },
        {
            "title": "Launch",
            "description": "Production deploy, monitoring, comms.",
            "priority": "urgent",
            "estimated_hours": 16,
            "depends_on": [4],
        },
    ],
    "milestones": [
        {"name": "Design lock-in", "target_offset_days": 7},
        {"name": "Feature complete", "target_offset_days": 21},
        {"name": "Launch", "target_offset_days": 30},
    ],
}


class WBSGenerator:
    def __init__(self, copilot: AICopilotService | None = None):
        self.copilot = copilot or get_copilot()

    async def generate(self, request: WBSRequest) -> WBSResult:
        user_prompt = (
            f"Goal: {request.goal}\n"
            f"Deadline: {request.deadline_days} days from today\n"
            f"Team size: {request.team_size}\n"
            "Produce 5-12 tasks and 2-4 milestones. JSON only."
        )
        result = await self.copilot.chat(
            messages=[
                ChatMessage(role="system", content=WBS_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_prompt),
            ],
            max_tokens=1500,
            temperature=0.2,
            json_mode=True,
        )

        parsed = _try_parse_json(result.text)
        if not parsed or not _looks_like_wbs(parsed):
            parsed = FALLBACK_WBS
            provider = "fallback-template"
            model = "fallback-v1"
        else:
            provider = result.provider
            model = result.model

        # Strip whitespace first, then drop anything that became empty so we
        # don't persist Task(title="") past the Pydantic schema's
        # min_length=1 contract.
        raw_tasks = parsed.get("tasks") or []
        if not isinstance(raw_tasks, list):
            raw_tasks = []
        tasks: list[GeneratedTask] = []
        for t in raw_tasks:
            if not isinstance(t, dict):
                continue
            title = str(t.get("title") or "").strip()[:255]
            if not title:
                continue
            tasks.append(
                GeneratedTask(
                    title=title,
                    description=str(t.get("description") or "").strip(),
                    priority=_clamp_priority(t.get("priority")),
                    estimated_hours=_clamp_int(
                        t.get("estimated_hours"), 1, 1000, default=8
                    ),
                    depends_on=_coerce_int_list(t.get("depends_on")),
                )
            )

        # Clamp every depends_on index into [0, len(tasks)) and drop self-refs
        # so the persistence layer can't introduce a bad FK.
        for idx, gt in enumerate(tasks):
            gt.depends_on = [d for d in gt.depends_on if 0 <= d < len(tasks) and d != idx]

        raw_milestones = parsed.get("milestones") or []
        if not isinstance(raw_milestones, list):
            raw_milestones = []
        milestones: list[GeneratedMilestone] = []
        for m in raw_milestones:
            if not isinstance(m, dict):
                continue
            name = str(m.get("name") or "").strip()[:255]
            if not name:
                continue
            milestones.append(
                GeneratedMilestone(
                    name=name,
                    target_offset_days=_clamp_int(
                        m.get("target_offset_days"),
                        1,
                        max(1, request.deadline_days),
                        default=request.deadline_days,
                    ),
                )
            )
        return WBSResult(
            tasks=tasks, milestones=milestones, provider=provider, model=model
        )


def _try_parse_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    # The model sometimes wraps JSON in code fences; strip them.
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to recover the first {...} block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _looks_like_wbs(d: dict[str, Any]) -> bool:
    return isinstance(d, dict) and isinstance(d.get("tasks"), list) and len(d["tasks"]) >= 1


_PRIORITIES = {"low", "medium", "high", "urgent"}


def _clamp_priority(value: Any) -> str:
    if isinstance(value, str) and value.lower() in _PRIORITIES:
        return value.lower()
    return "medium"


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _coerce_int_list(value: Any) -> list[int]:
    """Best-effort coercion of an LLM-emitted index list.

    Smaller models routinely stringify integers in JSON ("0", "1") or wrap
    them in floats (1.0). The previous implementation gated on
    `isinstance(d, int)` before calling `int(d)`, which silently dropped
    every stringified index and produced an empty dependency graph.
    """
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for d in value:
        try:
            out.append(int(d))
        except (TypeError, ValueError):
            continue
    return out


def milestone_target_date(offset_days: int, today: date | None = None) -> date:
    today = today or date.today()
    return today + timedelta(days=offset_days)
