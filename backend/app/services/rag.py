"""RAG over project content — semantic search + grounded Q&A.

Embedding: deterministic character-trigram hashing (no ML dependency,
deterministic, fast). Real sentence-transformer / OpenAI embeddings can
be swapped in by replacing `embed_text`; the storage + query path is
unchanged.

Why a hashing embedding instead of TF-IDF: doesn't require a corpus
fit, doesn't grow with vocab, and gives sensible cosine similarity
between short strings out of the box — perfect for a CRUD app that
needs *some* semantic signal without shipping a model file.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select

from app.models.embedding import EmbeddingChunk
from app.models.task import Task
from app.models.comment import Comment
from app.models.project import Project
from app.services.ai_copilot import ChatMessage, get_copilot


EMBED_DIM = 256


def _trigrams(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.lower().strip())
    if len(text) < 3:
        return [text] if text else []
    return [text[i : i + 3] for i in range(len(text) - 2)]


def embed_text(text: str) -> list[float]:
    """Hashed character-trigram vector, L2-normalized.

    Stable across processes (uses MD5 mod EMBED_DIM, not Python's salted
    hash()) so embeddings persisted from one run match queries from another.
    """
    vec = [0.0] * EMBED_DIM
    if not text:
        return vec
    for tri in _trigrams(text):
        h = int(hashlib.md5(tri.encode("utf-8")).hexdigest(), 16) % EMBED_DIM
        vec[h] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


@dataclass
class SearchHit:
    entity_type: str
    entity_id: UUID
    content: str
    score: float


async def index_workspace(
    db: AsyncSession, workspace_id: UUID
) -> int:
    """Re-index every (live) task + comment in the workspace.

    Returns the number of chunks written. Idempotent — wipes any existing
    rows for the workspace first so we don't accumulate dupes.
    """
    await db.execute(
        delete(EmbeddingChunk).where(EmbeddingChunk.workspace_id == workspace_id)
    )

    project_ids_rows = await db.execute(
        select(Project.id).where(
            Project.workspace_id == workspace_id, Project.deleted_at.is_(None)
        )
    )
    project_ids = [r[0] for r in project_ids_rows.all()]
    if not project_ids:
        await db.commit()
        return 0

    written = 0
    tasks_rows = await db.execute(
        select(Task).where(
            Task.project_id.in_(project_ids), Task.deleted_at.is_(None)
        )
    )
    for task in tasks_rows.scalars().all():
        content = f"{task.title}\n\n{task.description or ''}".strip()
        db.add(
            EmbeddingChunk(
                workspace_id=workspace_id,
                entity_type="task",
                entity_id=task.id,
                content=content,
                embedding=embed_text(content),
            )
        )
        written += 1

    comments_rows = await db.execute(
        select(Comment).join(Task, Task.id == Comment.task_id).where(
            Task.project_id.in_(project_ids), Task.deleted_at.is_(None)
        )
    )
    for c in comments_rows.scalars().all():
        db.add(
            EmbeddingChunk(
                workspace_id=workspace_id,
                entity_type="comment",
                entity_id=c.id,
                content=c.body,
                embedding=embed_text(c.body),
            )
        )
        written += 1

    await db.commit()
    return written


async def search(
    db: AsyncSession,
    workspace_id: UUID,
    query: str,
    *,
    limit: int = 10,
) -> list[SearchHit]:
    if not query.strip():
        return []
    q_vec = embed_text(query)
    rows = await db.execute(
        select(EmbeddingChunk).where(EmbeddingChunk.workspace_id == workspace_id)
    )
    chunks = list(rows.scalars().all())
    scored = [
        SearchHit(
            entity_type=c.entity_type,
            entity_id=c.entity_id,
            content=c.content,
            score=cosine(q_vec, c.embedding),
        )
        for c in chunks
    ]
    scored.sort(key=lambda h: h.score, reverse=True)
    return [h for h in scored[:limit] if h.score > 0]


async def ask(
    db: AsyncSession, workspace_id: UUID, question: str, *, top_k: int = 5
) -> dict:
    """RAG answer: retrieve, then ask the Copilot to ground its reply."""
    hits = await search(db, workspace_id, question, limit=top_k)
    if not hits:
        return {
            "answer": "No matching content was found in this workspace.",
            "citations": [],
            "provider": "no-context",
            "model": "n/a",
        }
    context = "\n---\n".join(
        f"[{h.entity_type}:{h.entity_id}] {h.content[:500]}" for h in hits
    )
    system = (
        "Answer the user's question using ONLY the provided context. "
        "Cite the entity IDs you used. If nothing in the context answers, say so."
    )
    user = f"Context:\n{context}\n\nQuestion: {question}"
    result = await get_copilot().chat(
        [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=user),
        ],
        max_tokens=600,
    )
    return {
        "answer": result.text,
        "citations": [
            {"entity_type": h.entity_type, "entity_id": str(h.entity_id), "score": round(h.score, 4)}
            for h in hits
        ],
        "provider": result.provider,
        "model": result.model,
    }
