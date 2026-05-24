import uuid
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.task import Task


class DependencyType(str, PyEnum):
    """Project-management standard dependency types.

    - FS (finish-to-start): successor starts only after predecessor finishes.
      This is the most common type and the default.
    - SS (start-to-start): successor starts only after predecessor starts.
    - FF (finish-to-finish): successor finishes only after predecessor finishes.
    - SF (start-to-finish): successor finishes only after predecessor starts.
    """
    FS = "finish_to_start"
    SS = "start_to_start"
    FF = "finish_to_finish"
    SF = "start_to_finish"


class TaskDependency(Base, TimestampMixin):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "task_id", "depends_on_task_id", "type",
            name="uq_task_dependency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[DependencyType] = mapped_column(
        Enum(DependencyType, name="dependencytype"),
        nullable=False,
        default=DependencyType.FS,
    )

    task: Mapped["Task"] = relationship(
        "Task", foreign_keys=[task_id], lazy="selectin"
    )
    depends_on: Mapped["Task"] = relationship(
        "Task", foreign_keys=[depends_on_task_id], lazy="selectin"
    )
