import uuid

from sqlalchemy import String, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin


class EmbeddingChunk(Base, TimestampMixin):
    """Vector-search chunk over project content (task titles + descriptions,
    comments). Stored as a JSON-serialized list[float] so the same row works
    on SQLite (dev) and Postgres (prod). When pgvector is available the
    column can be migrated to `vector(N)` without changing the application
    layer."""
    __tablename__ = "embedding_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    content: Mapped[str] = mapped_column(String(8000), nullable=False)
    embedding: Mapped[list] = mapped_column(JSON, nullable=False)
