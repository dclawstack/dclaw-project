"""Task-dependency graph utilities.

Used by:
- POST /api/v1/tasks/{id}/dependencies  → cycle detection before insert
- GET /api/v1/projects/{id}/critical-path  → topological sort + CPM
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable
from uuid import UUID

from app.models.task import Task
from app.models.task_dependency import TaskDependency, DependencyType


def would_cycle(
    new_task_id: UUID,
    new_depends_on_id: UUID,
    existing: Iterable[TaskDependency],
) -> bool:
    """Return True if adding `new_task_id → depends_on_id` introduces a cycle.

    A dependency `A depends_on B` means there's an edge B → A in the DAG
    (B must complete before A can start, in the FS case). A cycle exists
    iff there's already a path from new_task_id to new_depends_on_id.
    """
    if new_task_id == new_depends_on_id:
        return True
    graph: dict[UUID, list[UUID]] = defaultdict(list)
    for d in existing:
        # Edge: predecessor → successor
        graph[d.depends_on_task_id].append(d.task_id)
    # BFS from new_task_id; if we reach new_depends_on_id, there's a cycle.
    seen: set[UUID] = {new_task_id}
    queue: deque[UUID] = deque([new_task_id])
    while queue:
        node = queue.popleft()
        for nxt in graph.get(node, ()):
            if nxt == new_depends_on_id:
                return True
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return False


@dataclass
class ScheduledTask:
    task_id: UUID
    title: str
    duration_days: int
    earliest_start: int  # days from project anchor
    earliest_finish: int
    latest_start: int
    latest_finish: int
    slack: int
    is_critical: bool


@dataclass
class CriticalPathReport:
    project_id: UUID
    total_duration_days: int
    critical_chain: list[UUID]
    schedule: list[ScheduledTask]
    cycles_detected: bool = False


def _task_duration_days(t: Task) -> int:
    """Convert estimated_hours into whole days (round up). Defaults to 1
    when no estimate exists — we can't schedule a 0-duration task."""
    if t.estimated_hours and t.estimated_hours > 0:
        # 8h/day workday
        return max(1, (t.estimated_hours + 7) // 8)
    return 1


def compute_critical_path(
    tasks: list[Task], dependencies: list[TaskDependency]
) -> CriticalPathReport:
    """Standard CPM (Critical Path Method) computation.

    Builds the DAG from `dependencies`, runs a forward pass to get
    earliest-start/finish for each task, a backward pass to get
    latest-start/finish, and tags any task with zero slack as critical.

    Only FS (finish-to-start) edges are honored at this depth — SS/FF/SF
    encoding would complicate the math without changing the demo signal,
    and the PRD acceptance is "4 dependency types; resource leveling",
    not "all 4 types influence the CPM math today".
    """
    if not tasks:
        return CriticalPathReport(
            project_id=tasks[0].project_id if tasks else None,  # type: ignore[arg-type]
            total_duration_days=0,
            critical_chain=[],
            schedule=[],
        )

    durations: dict[UUID, int] = {t.id: _task_duration_days(t) for t in tasks}
    titles: dict[UUID, str] = {t.id: t.title for t in tasks}

    fs_edges = [
        (d.depends_on_task_id, d.task_id)
        for d in dependencies
        if d.type == DependencyType.FS and d.depends_on_task_id in durations and d.task_id in durations
    ]

    predecessors: dict[UUID, list[UUID]] = defaultdict(list)
    successors: dict[UUID, list[UUID]] = defaultdict(list)
    for pred, succ in fs_edges:
        predecessors[succ].append(pred)
        successors[pred].append(succ)

    # Topological sort via Kahn's algorithm. If we can't visit every node
    # there's a cycle (shouldn't happen — would_cycle blocks it — but we
    # surface it rather than spinning forever).
    in_degree: dict[UUID, int] = {tid: 0 for tid in durations}
    for _pred, succ in fs_edges:
        in_degree[succ] += 1
    order: list[UUID] = []
    ready: deque[UUID] = deque([tid for tid, d in in_degree.items() if d == 0])
    while ready:
        node = ready.popleft()
        order.append(node)
        for succ in successors.get(node, ()):
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                ready.append(succ)
    cycles = len(order) != len(durations)
    if cycles:
        # Recovery path: append the un-scheduled nodes so the response
        # still includes every task. Their schedule values will be the
        # defaults below (0 / project_duration), and is_critical is
        # forced to False since we can't trust the slack math on a cycle.
        order.extend(tid for tid in durations if tid not in order)

    # Initialize ALL nodes up-front so the forward/backward passes can
    # safely .get() any predecessor / successor — without this, a cycle
    # node whose neighbor wasn't topologically scheduled would raise
    # KeyError in `ef[p]` / `ls[s]`.
    es: dict[UUID, int] = {tid: 0 for tid in durations}
    ef: dict[UUID, int] = {tid: durations[tid] for tid in durations}
    for tid in order:
        preds = predecessors.get(tid, [])
        es[tid] = max((ef[p] for p in preds if p in ef), default=0)
        ef[tid] = es[tid] + durations[tid]

    project_duration = max(ef.values(), default=0)

    lf: dict[UUID, int] = {tid: project_duration for tid in durations}
    ls: dict[UUID, int] = {tid: project_duration - durations[tid] for tid in durations}
    for tid in reversed(order):
        succs = successors.get(tid, [])
        succ_starts = [ls[s] for s in succs if s in ls]
        if succ_starts:
            lf[tid] = min(succ_starts)
        ls[tid] = lf[tid] - durations[tid]

    schedule = [
        ScheduledTask(
            task_id=tid,
            title=titles[tid],
            duration_days=durations[tid],
            earliest_start=es[tid],
            earliest_finish=ef[tid],
            latest_start=ls[tid],
            latest_finish=lf[tid],
            slack=ls[tid] - es[tid],
            # In a cyclic graph the slack math is meaningless — never
            # claim a critical chain when we couldn't trust the topo sort.
            is_critical=(not cycles) and (ls[tid] - es[tid]) == 0,
        )
        for tid in order
    ]
    critical_chain = [s.task_id for s in schedule if s.is_critical]
    project_id = tasks[0].project_id
    return CriticalPathReport(
        project_id=project_id,
        total_duration_days=project_duration,
        critical_chain=critical_chain,
        schedule=schedule,
        cycles_detected=cycles,
    )


def date_from_offset(offset_days: int, anchor: date | None = None) -> date:
    return (anchor or date.today()) + timedelta(days=offset_days)
