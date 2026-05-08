import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Date, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class Milestone(Base):
    __tablename__ = "milestones"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default_factory=uuid.uuid4)
    completed: Mapped[bool] = mapped_column(default=False, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="milestones", lazy="selectin", init=False)
