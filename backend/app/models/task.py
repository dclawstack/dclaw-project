import uuid
from datetime import date
from typing import TYPE_CHECKING
from enum import Enum as PyEnum

from sqlalchemy import String, Text, Date, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class TaskStatus(str, PyEnum):
    todo = "todo"
    in_progress = "in_progress"
    review = "review"
    done = "done"


class TaskPriority(str, PyEnum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class Task(Base):
    __tablename__ = "tasks"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="taskstatus"), nullable=False, default=TaskStatus.todo
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, name="taskpriority"), nullable=False, default=TaskPriority.medium
    )

    project: Mapped["Project"] = relationship(back_populates="tasks", lazy="selectin")
