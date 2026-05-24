import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin
from app.models.project import project_tags
from app.models.task import task_tags

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.task import Task


class Tag(Base, TimestampMixin):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#64748b")

    projects: Mapped[list["Project"]] = relationship(
        secondary=project_tags, lazy="selectin", back_populates="tags"
    )
    tasks: Mapped[list["Task"]] = relationship(
        secondary=task_tags, lazy="selectin", back_populates="tags"
    )
