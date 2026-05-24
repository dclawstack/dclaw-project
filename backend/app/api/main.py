from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.core.logging import configure_logging, get_logger, request_id_middleware
from app.api.routes import health
from app.api.v1 import (
    auth_router,
    workspaces_router,
    projects_router,
    tasks_router,
    milestones_router,
    tags_router,
    ai_router,
    task_dependencies_router,
    project_dependencies_router,
    analytics_router,
    time_entries_router,
    notifications_router,
    events_router,
    agent_router,
    rag_router,
    risk_router,
    leveling_router,
    billing_router,
    integrations_router,
    documents_router,
    sprints_router,
)

configure_logging("DEBUG" if settings.debug else "INFO")
log = get_logger("dclaw.project")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup.begin", env=settings.app_env, sqlite=settings.is_sqlite)
    await init_db()
    log.info("startup.ready", database_url=settings.database_url.split("@")[-1])
    yield
    log.info("shutdown")


app = FastAPI(
    title=settings.app_name,
    description=(
        "DClaw Project — the autonomous project manager. "
        "AI-native project planning, task tracking, and risk prediction. "
        "Backed by FastAPI + SQLAlchemy 2.0 + (PostgreSQL | SQLite)."
    ),
    version="1.2.1",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "health", "description": "Liveness + readiness probes"},
        {"name": "auth", "description": "Registration, login, /me, workspace switch"},
        {"name": "workspaces", "description": "Workspace creation + listing"},
        {"name": "projects", "description": "Project CRUD, search, and stats"},
        {"name": "tasks", "description": "Task CRUD, subtasks, comments, bulk ops"},
        {"name": "milestones", "description": "Project milestone tracking"},
        {"name": "tags", "description": "Labels for projects + tasks"},
        {"name": "ai", "description": "AI Copilot — chat, WBS generation, project health"},
        {"name": "notifications", "description": "Bell + SSE real-time stream"},
        {"name": "integrations", "description": "Stripe billing + Slack + GitHub + Logto (stubs)"},
        {"name": "documents", "description": "Upload + AI summarization"},
        {"name": "sprints", "description": "Sprint planning + backlog"},
    ],
)

app.middleware("http")(request_id_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id"],
)

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(workspaces_router, prefix="/api/v1/workspaces", tags=["workspaces"])
app.include_router(projects_router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(tasks_router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(task_dependencies_router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(project_dependencies_router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(analytics_router, prefix="/api/v1/analytics/projects", tags=["projects"])
app.include_router(time_entries_router, prefix="/api/v1/time-entries", tags=["tasks"])
app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["notifications"])
app.include_router(events_router, prefix="/api/v1/events", tags=["notifications"])

# C2 surfaces
app.include_router(agent_router, prefix="/api/v1/ai", tags=["ai"])
app.include_router(rag_router, prefix="/api/v1/ai", tags=["ai"])
app.include_router(risk_router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(leveling_router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(billing_router, prefix="/api/v1/billing", tags=["integrations"])
app.include_router(integrations_router, prefix="/api/v1/integrations", tags=["integrations"])
app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(sprints_router, prefix="/api/v1/sprints", tags=["sprints"])
app.include_router(milestones_router, prefix="/api/v1/milestones", tags=["milestones"])
app.include_router(tags_router, prefix="/api/v1/tags", tags=["tags"])
app.include_router(ai_router, prefix="/api/v1/ai", tags=["ai"])
