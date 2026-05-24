from app.models.base import Base
from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.milestone import Milestone
from app.models.tag import Tag
from app.models.comment import Comment

# Wire up soft-delete cascades. The bulk-UPDATE form (see
# `BaseRepository.delete`) takes (child_model, fk_attr_name) pairs.
from app.repositories.base_repo import register_soft_delete_cascade

register_soft_delete_cascade(Project, (Task, "project_id"), (Milestone, "project_id"))
register_soft_delete_cascade(Task, (Task, "parent_task_id"))

__all__ = [
    "Base",
    "Project",
    "ProjectStatus",
    "Task",
    "TaskStatus",
    "TaskPriority",
    "Milestone",
    "Tag",
    "Comment",
]
