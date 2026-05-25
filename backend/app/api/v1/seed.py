"""
Seed / clear demo data for DClaw Project.

POST   /api/v1/seed  — wipe everything, then create a demo user + workspace
                       populated with realistic projects, tasks, milestones,
                       tags, and comments. Returns an access token so the
                       landing page can drop the visitor straight into the
                       populated dashboard.
DELETE /api/v1/seed  — wipe all data from every table (fresh state).

This whole module is a self-contained demo utility. To remove the feature,
delete this file and the two lines that register it in app/api/main.py
(plus the SeedControls block on the frontend landing page).
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, hash_password

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.milestone import Milestone
from app.models.tag import Tag
from app.models.comment import Comment
from app.models.time_entry import TimeEntry
from app.models.sprint import Sprint, SprintTask
from app.models.task_dependency import TaskDependency
from app.models.notification import Notification

router = APIRouter()

DEMO_EMAIL = "demo@dclaw.dev"
DEMO_PASSWORD = "demo1234"
DEMO_NAME = "Demo User"
DEMO_WORKSPACE = "Acme Product Team"

# Tables wiped on clear / re-seed, ordered child → parent so the wipe works
# even when ON DELETE CASCADE is not enforced (e.g. SQLite in tests).
_WIPE_ORDER = [
    TimeEntry,
    Comment,
    SprintTask,
    TaskDependency,
    Notification,
    Task,
    Milestone,
    Sprint,
    Tag,
    Project,
    WorkspaceMember,
    Workspace,
    User,
]


async def _wipe(db: AsyncSession) -> None:
    for model in _WIPE_ORDER:
        await db.execute(delete(model))


# ── Demo content definitions ──────────────────────────────────────────────────

_TAGS = [
    ("Frontend", "#3b82f6"),
    ("Backend", "#8b5cf6"),
    ("Design", "#ec4899"),
    ("Infra", "#f59e0b"),
    ("Research", "#10b981"),
    ("Bug", "#ef4444"),
]

ASSIGNEES = ["Alice Chen", "Bob Martinez", "Carol Diaz", DEMO_NAME]


def _project_defs(today: date):
    """Returns project blueprints. Dates are relative to `today` so the
    dashboard's due-today / overdue / completed widgets always have content."""
    return [
        dict(
            name="Mobile App Launch",
            description="Ship the v1.0 iOS + Android app to the public stores.",
            status=ProjectStatus.active,
            owner="Alice Chen",
            start_date=today - timedelta(days=40),
            end_date=today + timedelta(days=20),
            tags=["Frontend", "Design"],
            milestones=[
                ("Beta on TestFlight", today - timedelta(days=7), True),
                ("App Store submission", today + timedelta(days=10), False),
                ("Public launch", today + timedelta(days=20), False),
            ],
            tasks=[
                ("Build onboarding flow", TaskStatus.done, TaskPriority.high, "Alice Chen",
                 today - timedelta(days=5), today - timedelta(days=6), 16, ["Frontend"],
                 [("Design onboarding screens", TaskStatus.done, TaskPriority.medium, "Carol Diaz")]),
                ("Push notification service", TaskStatus.in_progress, TaskPriority.high, "Bob Martinez",
                 today, None, 12, ["Backend"], []),
                ("Fix crash on cold start", TaskStatus.in_progress, TaskPriority.urgent, "Bob Martinez",
                 today - timedelta(days=2), None, 6, ["Bug", "Backend"], []),
                ("App Store screenshots", TaskStatus.todo, TaskPriority.medium, "Carol Diaz",
                 today + timedelta(days=4), None, 4, ["Design"], []),
                ("Accessibility audit", TaskStatus.review, TaskPriority.medium, "Alice Chen",
                 today + timedelta(days=2), None, 8, ["Frontend"], []),
            ],
        ),
        dict(
            name="Website Redesign",
            description="Rebuild the marketing site on the new design system.",
            status=ProjectStatus.active,
            owner=DEMO_NAME,
            start_date=today - timedelta(days=20),
            end_date=today + timedelta(days=35),
            tags=["Design", "Frontend"],
            milestones=[
                ("Design system approved", today - timedelta(days=3), True),
                ("Homepage live", today + timedelta(days=15), False),
            ],
            tasks=[
                ("Implement new hero section", TaskStatus.in_progress, TaskPriority.high, "Carol Diaz",
                 today, None, 10, ["Frontend", "Design"], []),
                ("Migrate blog to MDX", TaskStatus.todo, TaskPriority.low, "Alice Chen",
                 today + timedelta(days=12), None, 14, ["Frontend"], []),
                ("SEO metadata pass", TaskStatus.todo, TaskPriority.medium, "Bob Martinez",
                 today - timedelta(days=1), None, 5, ["Research"], []),
                ("Set up analytics", TaskStatus.done, TaskPriority.medium, DEMO_NAME,
                 today - timedelta(days=4), today - timedelta(days=4), 3, ["Infra"], []),
            ],
        ),
        dict(
            name="API v2 Migration",
            description="Move all clients onto the versioned, paginated API v2.",
            status=ProjectStatus.planning,
            owner="Bob Martinez",
            start_date=today + timedelta(days=5),
            end_date=today + timedelta(days=60),
            tags=["Backend", "Infra"],
            milestones=[
                ("RFC sign-off", today + timedelta(days=5), False),
                ("v2 in staging", today + timedelta(days=30), False),
            ],
            tasks=[
                ("Draft migration RFC", TaskStatus.in_progress, TaskPriority.high, "Bob Martinez",
                 today + timedelta(days=3), None, 8, ["Research", "Backend"], []),
                ("Inventory v1 endpoints", TaskStatus.todo, TaskPriority.medium, "Alice Chen",
                 today + timedelta(days=7), None, 6, ["Backend"], []),
                ("Define deprecation timeline", TaskStatus.todo, TaskPriority.low, DEMO_NAME,
                 today + timedelta(days=10), None, 2, [], []),
            ],
        ),
        dict(
            name="Q1 Marketing Site",
            description="Landing pages and lead capture for the Q1 campaign.",
            status=ProjectStatus.completed,
            owner="Carol Diaz",
            start_date=today - timedelta(days=120),
            end_date=today - timedelta(days=30),
            tags=["Design", "Frontend"],
            milestones=[
                ("Campaign live", today - timedelta(days=35), True),
                ("Post-mortem", today - timedelta(days=28), True),
            ],
            tasks=[
                ("Build landing pages", TaskStatus.done, TaskPriority.high, "Carol Diaz",
                 today - timedelta(days=45), today - timedelta(days=46), 20, ["Frontend"], []),
                ("Wire up lead form", TaskStatus.done, TaskPriority.medium, "Alice Chen",
                 today - timedelta(days=40), today - timedelta(days=41), 6, ["Frontend", "Backend"], []),
            ],
        ),
        dict(
            name="Data Platform",
            description="Central warehouse + dashboards. Paused pending budget.",
            status=ProjectStatus.on_hold,
            owner="Alice Chen",
            start_date=today - timedelta(days=15),
            end_date=None,
            tags=["Infra", "Research"],
            milestones=[
                ("Vendor selection", today + timedelta(days=45), False),
            ],
            tasks=[
                ("Evaluate warehouse vendors", TaskStatus.review, TaskPriority.medium, "Alice Chen",
                 today - timedelta(days=3), None, 12, ["Research"], []),
                ("Cost model spreadsheet", TaskStatus.done, TaskPriority.low, DEMO_NAME,
                 today - timedelta(days=8), today - timedelta(days=9), 4, ["Research"], []),
            ],
        ),
    ]


_COMMENTS = [
    ("Push notification service", [
        ("Bob Martinez", "APNs cert is uploaded. Working through the FCM side now."),
        ("Alice Chen", "Nice — ping me when you want to test on a real device."),
    ]),
    ("Fix crash on cold start", [
        ("Bob Martinez", "Repro'd it: a nil unwrap in the cache warm-up path."),
    ]),
    ("Implement new hero section", [
        ("Carol Diaz", "Using the gradient token from the new design system."),
    ]),
]


# ── Route handlers ─────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def seed_data(db: AsyncSession = Depends(get_db)):
    """Reset to a fully-populated demo workspace and return a login token."""
    await _wipe(db)

    today = date.today()
    now = datetime.now(timezone.utc)

    # ── Demo user + workspace ────────────────────────────────────────────────
    user = User(
        email=DEMO_EMAIL,
        hashed_password=hash_password(DEMO_PASSWORD),
        full_name=DEMO_NAME,
    )
    db.add(user)
    await db.flush()

    workspace = Workspace(name=DEMO_WORKSPACE, slug="acme-product-team")
    db.add(workspace)
    await db.flush()

    db.add(WorkspaceMember(
        workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.owner
    ))

    # ── Tags ─────────────────────────────────────────────────────────────────
    tags: dict[str, Tag] = {}
    for name, color in _TAGS:
        tag = Tag(workspace_id=workspace.id, name=name, color=color)
        db.add(tag)
        tags[name] = tag
    await db.flush()

    # ── Projects + milestones + tasks + comments ─────────────────────────────
    comments_by_title: dict[str, list[tuple[str, str]]] = dict(_COMMENTS)
    counts = {"projects": 0, "milestones": 0, "tasks": 0, "subtasks": 0, "comments": 0}

    for pdef in _project_defs(today):
        project = Project(
            workspace_id=workspace.id,
            name=pdef["name"],
            description=pdef["description"],
            status=pdef["status"],
            owner=pdef["owner"],
            start_date=pdef["start_date"],
            end_date=pdef["end_date"],
            tags=[tags[t] for t in pdef["tags"]],
        )
        db.add(project)
        await db.flush()
        counts["projects"] += 1

        for name, target, done in pdef["milestones"]:
            db.add(Milestone(
                project_id=project.id, name=name, target_date=target, completed=done,
            ))
            counts["milestones"] += 1

        for (title, status, priority, assignee, due, completed_at,
             est, task_tags, subtasks) in pdef["tasks"]:
            task = Task(
                project_id=project.id,
                title=title,
                status=status,
                priority=priority,
                assignee=assignee,
                due_date=due,
                completed_at=completed_at,
                estimated_hours=est,
                tags=[tags[t] for t in task_tags],
            )
            db.add(task)
            await db.flush()
            counts["tasks"] += 1

            for sub_title, sub_status, sub_priority, sub_assignee in subtasks:
                db.add(Task(
                    project_id=project.id,
                    parent_task_id=task.id,
                    title=sub_title,
                    status=sub_status,
                    priority=sub_priority,
                    assignee=sub_assignee,
                ))
                counts["subtasks"] += 1

            for author, body in comments_by_title.get(title, []):
                db.add(Comment(task_id=task.id, author=author, body=body))
                counts["comments"] += 1

            # A couple of logged time entries on the in-progress work.
            if status == TaskStatus.in_progress:
                db.add(TimeEntry(
                    task_id=task.id, user_id=user.id,
                    started_at=now - timedelta(hours=3),
                    ended_at=now - timedelta(hours=1),
                    duration_seconds=2 * 3600,
                    billable=True,
                    notes="Focus block",
                ))

    await db.commit()

    token = create_access_token(
        subject=str(user.id), extra_claims={"ws": str(workspace.id)}
    )
    return {
        "seeded": True,
        "access_token": token,
        "demo_email": DEMO_EMAIL,
        "demo_password": DEMO_PASSWORD,
        "workspace": workspace.name,
        **counts,
    }


@router.delete("", status_code=200)
async def clear_data(db: AsyncSession = Depends(get_db)):
    """Wipe all data from every table — back to a clean install."""
    await _wipe(db)
    await db.commit()
    return {"cleared": True}
