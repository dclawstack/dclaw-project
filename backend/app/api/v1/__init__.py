from app.api.v1.projects import router as projects_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.milestones import router as milestones_router

__all__ = [
    "projects_router",
    "tasks_router",
    "milestones_router",
]
