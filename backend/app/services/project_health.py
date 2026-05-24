"""Project health scoring — the hero metric for the YC pitch.

Hybrid signal: a deterministic 0-100 score from observable project state
(overdue %, milestone slip, unassigned high-priority work, velocity proxy),
plus an LLM-written one-paragraph narrative when a Copilot is available.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from app.models.task import Task, TaskStatus, TaskPriority
from app.models.milestone import Milestone
from app.models.project import Project


@dataclass
class HealthSignal:
    label: str
    weight: float  # how much this signal moves the score, 0-1
    penalty: float  # 0 (perfect) → 1 (worst)


@dataclass
class HealthReport:
    score: int  # 0-100
    status: str  # "green" | "yellow" | "red"
    narrative: str
    signals: list[HealthSignal]
    top_risks: list[str]


def _open_tasks(tasks: Iterable[Task]) -> list[Task]:
    return [t for t in tasks if t.status != TaskStatus.done and t.deleted_at is None]


def _ratio(numer: int, denom: int) -> float:
    return 0.0 if denom == 0 else numer / denom


def compute_health(project: Project, today: date | None = None) -> HealthReport:
    today = today or date.today()
    tasks = list(project.active_tasks)
    open_tasks = _open_tasks(tasks)
    total_tasks = len(tasks)

    overdue = [t for t in open_tasks if t.due_date and t.due_date < today]
    due_soon = [
        t
        for t in open_tasks
        if t.due_date and 0 <= (t.due_date - today).days <= 7
    ]
    unassigned_high = [
        t
        for t in open_tasks
        if t.assignee in (None, "")
        and t.priority in (TaskPriority.high, TaskPriority.urgent)
    ]

    completed_pct = _ratio(total_tasks - len(open_tasks), total_tasks)

    milestones = list(project.active_milestones)
    slipped_milestones = [
        m for m in milestones if not m.completed and m.target_date < today
    ]
    upcoming_milestones = [
        m
        for m in milestones
        if not m.completed and 0 <= (m.target_date - today).days <= 14
    ]

    signals: list[HealthSignal] = [
        HealthSignal(
            label="Overdue tasks",
            weight=0.30,
            penalty=min(1.0, _ratio(len(overdue), max(total_tasks, 1)) * 3),
        ),
        HealthSignal(
            label="Slipped milestones",
            weight=0.25,
            penalty=min(1.0, _ratio(len(slipped_milestones), max(len(milestones), 1)) * 2),
        ),
        HealthSignal(
            label="Unassigned high-priority work",
            weight=0.15,
            penalty=min(1.0, _ratio(len(unassigned_high), max(total_tasks, 1)) * 4),
        ),
        HealthSignal(
            label="Crunch window (next 7d)",
            weight=0.15,
            penalty=min(1.0, _ratio(len(due_soon), max(len(open_tasks), 1)) * 1.5),
        ),
        HealthSignal(
            label="Progress (inverse of completion)",
            weight=0.15,
            penalty=max(0.0, 0.6 - completed_pct),  # rewards >60% complete
        ),
    ]

    weighted_penalty = sum(s.weight * s.penalty for s in signals)
    score = max(0, min(100, round((1 - weighted_penalty) * 100)))

    if score >= 75:
        status = "green"
    elif score >= 50:
        status = "yellow"
    else:
        status = "red"

    top_risks: list[str] = []
    if overdue:
        top_risks.append(f"{len(overdue)} overdue task(s)")
    if slipped_milestones:
        top_risks.append(
            f"{len(slipped_milestones)} milestone(s) past target without completion"
        )
    if unassigned_high:
        top_risks.append(
            f"{len(unassigned_high)} high/urgent task(s) without an owner"
        )
    if upcoming_milestones and not project.tasks:
        top_risks.append("Milestone within 2 weeks but no tasks defined")

    narrative = _heuristic_narrative(
        project, score, status, overdue, slipped_milestones, unassigned_high
    )

    return HealthReport(
        score=score,
        status=status,
        narrative=narrative,
        signals=signals,
        top_risks=top_risks,
    )


def _heuristic_narrative(
    project: Project,
    score: int,
    status: str,
    overdue: list[Task],
    slipped_milestones: list[Milestone],
    unassigned_high: list[Task],
) -> str:
    bits: list[str] = [f"Health is {status.upper()} ({score}/100)."]
    if overdue:
        bits.append(
            f"{len(overdue)} task(s) are past their due date — re-plan or reassign."
        )
    if slipped_milestones:
        bits.append(
            f"{len(slipped_milestones)} milestone(s) have slipped; consider moving the target or adding capacity."
        )
    if unassigned_high:
        bits.append(
            f"{len(unassigned_high)} high-priority task(s) still lack an owner."
        )
    if not (overdue or slipped_milestones or unassigned_high):
        bits.append("No blocking risk signals detected — keep momentum.")
    return " ".join(bits)
