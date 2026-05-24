"""Predictive risk model — probability of slippage in the next N days.

YC framing: the *defensible* AI. Every project run accrues training
features (snapshots of overdue%, velocity, dep depth) labeled with
whether the project actually slipped. As the dataset grows, the model
sharpens. Day-one baseline is a hand-tuned logistic on observable
features so the API contract is stable and the model can be swapped
later without changing callers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from app.models.task import Task, TaskStatus
from app.models.milestone import Milestone


@dataclass
class RiskFeatures:
    overdue_ratio: float       # 0..1
    avg_slack_days: float      # >= 0 (or 0 when unknown)
    velocity_trend: float      # -1 (decelerating) .. 1 (accelerating)
    unassigned_critical: int
    open_dep_chain_depth: int
    days_to_deadline: int      # negative when past
    milestone_slip_count: int


@dataclass
class RiskForecast:
    p_slip_1w: float
    p_slip_2w: float
    p_slip_4w: float
    top_factors: list[str]
    features: RiskFeatures


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def compute_features(
    tasks: list[Task],
    milestones: list[Milestone],
    *,
    deadline: date | None = None,
    today: date | None = None,
) -> RiskFeatures:
    today = today or date.today()
    tasks = [t for t in tasks if t.deleted_at is None]
    open_tasks = [t for t in tasks if t.status != TaskStatus.done]
    overdue = [t for t in open_tasks if t.due_date and t.due_date < today]
    overdue_ratio = (len(overdue) / max(len(tasks), 1)) if tasks else 0.0

    # Velocity trend: ratio of completions in last 7d vs 8-14d before.
    recent_done = sum(
        1
        for t in tasks
        if t.status == TaskStatus.done
        and t.completed_at
        and (today - t.completed_at).days <= 7
    )
    older_done = sum(
        1
        for t in tasks
        if t.status == TaskStatus.done
        and t.completed_at
        and 7 < (today - t.completed_at).days <= 14
    )
    if recent_done == 0 and older_done == 0:
        velocity_trend = 0.0
    else:
        velocity_trend = (recent_done - older_done) / max(recent_done + older_done, 1)

    unassigned_critical = sum(
        1
        for t in open_tasks
        if not t.assignee and t.priority.value in ("high", "urgent")
    )
    # Depth proxy: longest chain via parent_task_id
    chain_depth = 0
    for t in open_tasks:
        depth = 0
        cursor = t.parent_task_id
        seen: set = set()
        while cursor and cursor not in seen and depth < 50:
            seen.add(cursor)
            depth += 1
            parent = next((x for x in tasks if x.id == cursor), None)
            cursor = parent.parent_task_id if parent else None
        chain_depth = max(chain_depth, depth)

    days_to_deadline = (deadline - today).days if deadline else 30

    milestone_slip_count = sum(
        1 for m in milestones if not m.completed and m.target_date < today
    )

    return RiskFeatures(
        overdue_ratio=overdue_ratio,
        avg_slack_days=0.0,
        velocity_trend=velocity_trend,
        unassigned_critical=unassigned_critical,
        open_dep_chain_depth=chain_depth,
        days_to_deadline=days_to_deadline,
        milestone_slip_count=milestone_slip_count,
    )


def _logit(features: RiskFeatures, *, horizon_days: int) -> tuple[float, list[tuple[str, float]]]:
    """Hand-tuned baseline. Each contribution is recorded so we can
    surface "top factors" honestly."""
    contribs: list[tuple[str, float]] = []
    intercept = -1.5  # default low-risk
    contribs.append(("baseline", intercept))

    if features.overdue_ratio > 0:
        v = 4.0 * features.overdue_ratio
        contribs.append(("overdue_ratio", v))
    if features.unassigned_critical > 0:
        v = 0.6 * features.unassigned_critical
        contribs.append(("unassigned_critical", v))
    if features.velocity_trend < 0:
        v = 1.5 * abs(features.velocity_trend)
        contribs.append(("velocity_decelerating", v))
    if features.milestone_slip_count > 0:
        v = 1.0 * features.milestone_slip_count
        contribs.append(("milestone_slips", v))
    if features.open_dep_chain_depth > 4:
        v = 0.4 * (features.open_dep_chain_depth - 4)
        contribs.append(("long_dependency_chain", v))
    # Time pressure: closer to deadline → higher risk.
    if features.days_to_deadline <= 0:
        contribs.append(("past_deadline", 2.0))
    elif features.days_to_deadline < horizon_days:
        v = 1.0 * (horizon_days - features.days_to_deadline) / horizon_days
        contribs.append(("approaching_deadline", v))

    logit = sum(c for _, c in contribs)
    return logit, contribs


def predict_risk(
    tasks: list[Task],
    milestones: list[Milestone],
    *,
    deadline: date | None = None,
) -> RiskForecast:
    features = compute_features(tasks, milestones, deadline=deadline)
    forecasts: dict[int, tuple[float, list[tuple[str, float]]]] = {}
    for days in (7, 14, 28):
        forecasts[days] = _logit(features, horizon_days=days)

    p1, contribs1 = forecasts[7]
    p2, _ = forecasts[14]
    p3, _ = forecasts[28]

    # Surface the 3 biggest positive contributors as top factors.
    risk_contribs = [
        (name, v) for name, v in contribs1 if name != "baseline" and v > 0
    ]
    risk_contribs.sort(key=lambda x: x[1], reverse=True)
    top_factors = [
        name.replace("_", " ").capitalize()
        for name, _ in risk_contribs[:3]
    ]

    return RiskForecast(
        p_slip_1w=round(_sigmoid(p1), 3),
        p_slip_2w=round(_sigmoid(p2), 3),
        p_slip_4w=round(_sigmoid(p3), 3),
        top_factors=top_factors,
        features=features,
    )
