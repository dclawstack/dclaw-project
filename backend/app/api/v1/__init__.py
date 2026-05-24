from app.api.v1.auth import router as auth_router
from app.api.v1.auth import workspaces_router
from app.api.v1.projects import router as projects_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.milestones import router as milestones_router
from app.api.v1.tags import router as tags_router
from app.api.v1.ai import router as ai_router
from app.api.v1.dependencies import router as task_dependencies_router
from app.api.v1.dependencies import project_scoped_router as project_dependencies_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.time_entries import router as time_entries_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.notifications import events_router
from app.api.v1.c2_routes import (
    agent_router,
    rag_router,
    risk_router,
    leveling_router,
    billing_router,
    integrations_router,
    documents_router,
    sprints_router,
)

__all__ = [
    "auth_router",
    "workspaces_router",
    "projects_router",
    "tasks_router",
    "milestones_router",
    "tags_router",
    "ai_router",
    "task_dependencies_router",
    "project_dependencies_router",
    "analytics_router",
    "time_entries_router",
    "notifications_router",
    "events_router",
    "agent_router",
    "rag_router",
    "risk_router",
    "leveling_router",
    "billing_router",
    "integrations_router",
    "documents_router",
    "sprints_router",
]
