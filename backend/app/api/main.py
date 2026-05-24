from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.core.logging import configure_logging, get_logger, request_id_middleware
from app.api.routes import health
from app.api.v1 import (
    projects_router,
    tasks_router,
    milestones_router,
    tags_router,
    ai_router,
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
    version="1.2.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "health", "description": "Liveness + readiness probes"},
        {"name": "projects", "description": "Project CRUD, search, and stats"},
        {"name": "tasks", "description": "Task CRUD, subtasks, comments, bulk ops"},
        {"name": "milestones", "description": "Project milestone tracking"},
        {"name": "tags", "description": "Labels for projects + tasks"},
        {"name": "ai", "description": "AI Copilot — chat, WBS generation, project health"},
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
app.include_router(projects_router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(tasks_router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(milestones_router, prefix="/api/v1/milestones", tags=["milestones"])
app.include_router(tags_router, prefix="/api/v1/tags", tags=["tags"])
app.include_router(ai_router, prefix="/api/v1/ai", tags=["ai"])
