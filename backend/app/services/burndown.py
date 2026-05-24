"""Burndown + velocity computation from task completion timestamps."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from app.models.task import Task, TaskStatus


@dataclass
class BurndownPoint:
    day: date
    remaining: int
    completed: int


@dataclass
class BurndownReport:
    start: date
    end: date
    total: int
    points: list[BurndownPoint]
    velocity_per_week: float  # avg completions per week over the window


def compute_burndown(
    tasks: Iterable[Task],
    *,
    start: date | None = None,
    end: date | None = None,
) -> BurndownReport:
    tasks = [t for t in tasks if t.deleted_at is None]
    today = date.today()
    end = end or today
    if start is None:
        # Default window: from earliest task created_at (date portion) or
        # 14 days before today, whichever is earlier.
        earliest = min(
            (t.created_at.date() for t in tasks if t.created_at is not None),
            default=end - timedelta(days=14),
        )
        start = min(earliest, end - timedelta(days=14))

    total = len(tasks)
    # For burndown we model: how many tasks remained open at end-of-day on each day?
    # A task is open on day D if it was created on or before D and (not done OR
    # completed_at > D).
    completed_by_day: Counter[date] = Counter()
    for t in tasks:
        if t.status == TaskStatus.done and t.completed_at:
            completed_by_day[t.completed_at] += 1

    points: list[BurndownPoint] = []
    cumulative = 0
    day = start
    while day <= end:
        cumulative += completed_by_day.get(day, 0)
        # Remaining = total at end of window minus completions up to this day.
        # This treats `total` as the scope baseline so adding tasks later
        # doesn't artificially flatten the burndown — it does increase total,
        # which is what users expect to see ("scope creep").
        remaining = total - cumulative
        points.append(
            BurndownPoint(day=day, remaining=remaining, completed=cumulative)
        )
        day += timedelta(days=1)

    window_days = max(1, (end - start).days + 1)
    velocity = sum(completed_by_day.values()) / window_days * 7.0
    return BurndownReport(
        start=start, end=end, total=total, points=points, velocity_per_week=round(velocity, 2)
    )
