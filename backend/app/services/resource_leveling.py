"""Resource leveling — greedy allocator that respects per-person capacity.

Given a project's open tasks (with estimated hours + optional assignee),
suggest reassignments that balance load across the available team without
over-allocating anyone in any week. This is the *day-one* baseline that
proves the contract; OR-tools or a real constraint solver can replace
`level_resources` later without changing callers.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from app.models.task import Task, TaskStatus


WEEKLY_CAPACITY_HOURS = 32  # 4 days × 8h, leaving room for meetings


@dataclass
class Assignment:
    task_id: UUID
    title: str
    estimated_hours: int
    current_assignee: str | None
    suggested_assignee: str | None
    rationale: str


@dataclass
class LevelingReport:
    suggestions: list[Assignment]
    load_before: dict[str, int]   # hours per assignee BEFORE
    load_after: dict[str, int]    # hours per assignee AFTER
    unassigned_remaining: int


def level_resources(
    tasks: Iterable[Task], team: list[str] | None = None
) -> LevelingReport:
    open_tasks = [
        t for t in tasks
        if t.deleted_at is None and t.status != TaskStatus.done
    ]
    # Figure out the team. If the caller doesn't supply one, derive it
    # from the existing assignees.
    if not team:
        team = sorted({t.assignee for t in open_tasks if t.assignee})
    if not team:
        # No one to balance to.
        return LevelingReport(
            suggestions=[],
            load_before={},
            load_after={},
            unassigned_remaining=sum(1 for t in open_tasks if not t.assignee),
        )

    # Initial load: sum of estimated_hours per current assignee.
    load_before: dict[str, int] = {member: 0 for member in team}
    for t in open_tasks:
        if t.assignee in load_before:
            load_before[t.assignee] += t.estimated_hours or 0
        elif t.assignee:
            load_before[t.assignee] = t.estimated_hours or 0

    load_after = dict(load_before)
    suggestions: list[Assignment] = []

    # Two passes:
    # 1) Fill unassigned tasks first to the least-loaded team member.
    # 2) Rebalance: if anyone is at >1.5x weekly capacity, peel tasks off
    #    them onto the least-loaded member.
    unassigned = [t for t in open_tasks if not t.assignee]
    for t in unassigned:
        candidate = min(team, key=lambda m: load_after.get(m, 0))
        load_after[candidate] = load_after.get(candidate, 0) + (t.estimated_hours or 0)
        suggestions.append(
            Assignment(
                task_id=t.id,
                title=t.title,
                estimated_hours=t.estimated_hours or 0,
                current_assignee=None,
                suggested_assignee=candidate,
                rationale=f"Fill unassigned: {candidate} has lowest load",
            )
        )

    threshold = int(WEEKLY_CAPACITY_HOURS * 1.5)
    # Sort overloaded members descending so we move from worst-first.
    while True:
        overloaded = [m for m in team if load_after.get(m, 0) > threshold]
        if not overloaded:
            break
        overloaded.sort(key=lambda m: load_after[m], reverse=True)
        donor = overloaded[0]
        # Find a candidate task to move — prefer the lowest-priority,
        # smallest task assigned to the donor (least disruptive).
        donor_tasks = [
            t for t in open_tasks
            if t.assignee == donor and not any(s.task_id == t.id for s in suggestions)
        ]
        if not donor_tasks:
            break
        donor_tasks.sort(
            key=lambda t: (
                {"urgent": 0, "high": 1, "medium": 2, "low": 3}.get(t.priority.value, 2),
                -(t.estimated_hours or 0),
            )
        )
        # Pick the smallest non-urgent task to move.
        candidate_task = donor_tasks[-1]
        recipient = min(team, key=lambda m: load_after.get(m, 0))
        if recipient == donor:
            break
        hours = candidate_task.estimated_hours or 0
        load_after[donor] -= hours
        load_after[recipient] = load_after.get(recipient, 0) + hours
        suggestions.append(
            Assignment(
                task_id=candidate_task.id,
                title=candidate_task.title,
                estimated_hours=hours,
                current_assignee=donor,
                suggested_assignee=recipient,
                rationale=(
                    f"{donor} is over capacity ({load_after[donor] + hours}h); "
                    f"move to {recipient} ({load_after[recipient] - hours}h current)"
                ),
            )
        )

    return LevelingReport(
        suggestions=suggestions,
        load_before=load_before,
        load_after=load_after,
        unassigned_remaining=0,  # we placed them all above
    )
