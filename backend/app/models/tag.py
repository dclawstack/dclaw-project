import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin
from app.models.project import project_tags
from app.models.task import task_tags

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.task import Task
    from app.models.workspace import Workspace


class Tag(Base, TimestampMixin):
    __tablename__ = "tags"
    __table_args__ = (
        # Tag names are unique PER WORKSPACE, not globally — two tenants
        # may both have a "design" tag and they don't bleed into each other.
        UniqueConstraint("workspace_id", "name", name="uq_tags_workspace_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#64748b")

    workspace: Mapped["Workspace"] = relationship("Workspace", lazy="noload")
    projects: Mapped[list["Project"]] = relationship(
        secondary=project_tags, lazy="selectin", back_populates="tags"
    )
    tasks: Mapped[list["Task"]] = relationship(
        secondary=task_tags, lazy="selectin", back_populates="tags"
    )
