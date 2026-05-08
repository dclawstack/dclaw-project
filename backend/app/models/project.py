import uuid
from datetime import date
from typing import TYPE_CHECKING
from enum import Enum as PyEnum

from sqlalchemy import String, Text, Date, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.milestone import Milestone


class ProjectStatus(str, PyEnum):
    planning = "planning"
    active = "active"
    on_hold = "on_hold"
    completed = "completed"
    cancelled = "cancelled"


class Project(Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default_factory=uuid.uuid4)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="projectstatus"), nullable=False, default=ProjectStatus.planning
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project", lazy="selectin", cascade="all, delete-orphan"
    )
    milestones: Mapped[list["Milestone"]] = relationship(
        back_populates="project", lazy="selectin", cascade="all, delete-orphan"
    )
