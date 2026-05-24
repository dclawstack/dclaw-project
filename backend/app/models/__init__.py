from app.models.base import Base
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.milestone import Milestone
from app.models.tag import Tag
from app.models.comment import Comment
from app.models.task_dependency import TaskDependency, DependencyType
from app.models.time_entry import TimeEntry
from app.models.notification import Notification, NotificationKind
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.embedding import EmbeddingChunk
from app.models.document import Document
from app.models.sprint import Sprint, SprintTask

# Wire up soft-delete cascades. The bulk-UPDATE form (see
# `BaseRepository.delete`) takes (child_model, fk_attr_name) pairs.
from app.repositories.base_repo import register_soft_delete_cascade

register_soft_delete_cascade(Project, (Task, "project_id"), (Milestone, "project_id"))
register_soft_delete_cascade(Task, (Task, "parent_task_id"))

__all__ = [
    "Base",
    "User",
    "Workspace",
    "WorkspaceMember",
    "WorkspaceRole",
    "Project",
    "ProjectStatus",
    "Task",
    "TaskStatus",
    "TaskPriority",
    "Milestone",
    "Tag",
    "Comment",
    "TaskDependency",
    "DependencyType",
    "TimeEntry",
    "Notification",
    "NotificationKind",
    "AgentRun",
    "AgentRunStatus",
    "EmbeddingChunk",
    "Document",
    "Sprint",
    "SprintTask",
]
