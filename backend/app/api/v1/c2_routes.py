"""C2 routers: agent, RAG, risk model, resource leveling, integrations,
documents, sprints. Grouped here to keep the wiring concise; each surface
is small and stays close to its service module."""
from __future__ import annotations

import os
import uuid
from datetime import date
from pathlib import Path
from typing import List
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import AuthContext, require_workspace
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.document import Document
from app.models.sprint import Sprint, SprintTask
from app.models.task import Task
from app.repositories.project_repo import ProjectRepository
from app.repositories.task_repo import TaskRepository
from app.services.agent_planner import run_planner_agent
from app.services.integrations import (
    get_github,
    get_logto,
    get_slack,
    get_stripe,
)
from app.services.rag import ask as rag_ask
from app.services.rag import index_workspace, search as rag_search
from app.services.resource_leveling import level_resources
from app.services.risk_model import predict_risk
from app.services.ai_copilot import ChatMessage, get_copilot


# ---- Routers --------------------------------------------------------------


agent_router = APIRouter()
rag_router = APIRouter()
risk_router = APIRouter()
leveling_router = APIRouter()
billing_router = APIRouter()
integrations_router = APIRouter()
documents_router = APIRouter()
sprints_router = APIRouter()


# ---- helpers --------------------------------------------------------------


async def _project_or_404(db: AsyncSession, project_id: UUID, ctx: AuthContext):
    p = await ProjectRepository(db).get_by_id_in_workspace(project_id, ctx.workspace.id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


# ---- 6.1 Agent ------------------------------------------------------------


class AgentRunRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=2000)
    project_id: UUID | None = None
    max_steps: int = Field(default=6, ge=1, le=6)


class AgentStepRead(BaseModel):
    name: str
    output: dict | str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int


class AgentRunRead(BaseModel):
    id: UUID
    goal: str
    status: AgentRunStatus
    steps: list[AgentStepRead]
    final_output: dict
    tokens_in: int
    tokens_out: int
    latency_ms: int

    model_config = ConfigDict(from_attributes=True)


@agent_router.post("/agent/plan", response_model=AgentRunRead)
async def run_agent(
    body: AgentRunRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    if body.project_id:
        await _project_or_404(db, body.project_id, ctx)
    trace = await run_planner_agent(body.goal, max_steps=body.max_steps)
    run = AgentRun(
        workspace_id=ctx.workspace.id,
        project_id=body.project_id,
        goal=body.goal,
        status=AgentRunStatus.succeeded,
        steps=[
            {
                "name": s.name,
                "output": s.output,
                "provider": s.provider,
                "model": s.model,
                "tokens_in": s.tokens_in,
                "tokens_out": s.tokens_out,
                "latency_ms": s.latency_ms,
            }
            for s in trace.steps
        ],
        tokens_in=trace.tokens_in,
        tokens_out=trace.tokens_out,
        latency_ms=trace.latency_ms,
        final_output=trace.final,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


@agent_router.get("/agent/runs", response_model=list[AgentRunRead])
async def list_agent_runs(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    rows = await db.execute(
        select(AgentRun)
        .where(AgentRun.workspace_id == ctx.workspace.id)
        .order_by(AgentRun.created_at.desc())
        .limit(50)
    )
    return list(rows.scalars().all())


# ---- 6.2 RAG --------------------------------------------------------------


class SearchHitRead(BaseModel):
    entity_type: str
    entity_id: UUID
    content: str
    score: float


class SearchResponse(BaseModel):
    hits: list[SearchHitRead]


class AskResponse(BaseModel):
    answer: str
    citations: list[dict]
    provider: str
    model: str


@rag_router.post("/reindex", summary="Re-index all task/comment content for the active workspace")
async def reindex(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    n = await index_workspace(db, ctx.workspace.id)
    return {"chunks": n}


@rag_router.get("/search", response_model=SearchResponse)
async def semantic_search(
    q: str = Query(min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    hits = await rag_search(db, ctx.workspace.id, q, limit=limit)
    return SearchResponse(
        hits=[
            SearchHitRead(
                entity_type=h.entity_type,
                entity_id=h.entity_id,
                content=h.content,
                score=round(h.score, 4),
            )
            for h in hits
        ]
    )


@rag_router.post("/ask", response_model=AskResponse)
async def grounded_ask(
    body: dict,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    answer = await rag_ask(db, ctx.workspace.id, question, top_k=int(body.get("top_k", 5)))
    return AskResponse(**answer)


# ---- 6.5 Risk model -------------------------------------------------------


class RiskFeaturesRead(BaseModel):
    overdue_ratio: float
    avg_slack_days: float
    velocity_trend: float
    unassigned_critical: int
    open_dep_chain_depth: int
    days_to_deadline: int
    milestone_slip_count: int


class RiskForecastRead(BaseModel):
    project_id: UUID
    p_slip_1w: float
    p_slip_2w: float
    p_slip_4w: float
    top_factors: list[str]
    features: RiskFeaturesRead


@risk_router.get(
    "/{project_id}/risk-forecast", response_model=RiskForecastRead
)
async def project_risk_forecast(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    project = await _project_or_404(db, project_id, ctx)
    forecast = predict_risk(
        list(project.active_tasks),
        list(project.active_milestones),
        deadline=project.end_date,
    )
    return RiskForecastRead(
        project_id=project_id,
        p_slip_1w=forecast.p_slip_1w,
        p_slip_2w=forecast.p_slip_2w,
        p_slip_4w=forecast.p_slip_4w,
        top_factors=forecast.top_factors,
        features=RiskFeaturesRead(**forecast.features.__dict__),
    )


# ---- 6.4 Resource leveling ------------------------------------------------


class LevelingRequest(BaseModel):
    team: list[str] | None = None  # e.g. ["alice", "bob", "carol"]


class AssignmentRead(BaseModel):
    task_id: UUID
    title: str
    estimated_hours: int
    current_assignee: str | None
    suggested_assignee: str | None
    rationale: str


class LevelingResponse(BaseModel):
    project_id: UUID
    suggestions: list[AssignmentRead]
    load_before: dict[str, int]
    load_after: dict[str, int]


@leveling_router.post(
    "/{project_id}/optimize-resources", response_model=LevelingResponse
)
async def optimize_resources(
    project_id: UUID,
    body: LevelingRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    project = await _project_or_404(db, project_id, ctx)
    report = level_resources(list(project.active_tasks), team=body.team)
    return LevelingResponse(
        project_id=project_id,
        suggestions=[AssignmentRead(**s.__dict__) for s in report.suggestions],
        load_before=report.load_before,
        load_after=report.load_after,
    )


# ---- 6.6 Stripe billing ---------------------------------------------------


@billing_router.post("/usage", summary="Record a usage event for the active workspace")
async def record_usage(
    body: dict,
    ctx: AuthContext = Depends(require_workspace),
):
    metric = body.get("metric") or "ai_call"
    quantity = int(body.get("quantity", 1))
    event = get_stripe().record_usage(
        workspace_id=str(ctx.workspace.id), metric=metric, quantity=quantity
    )
    return event.__dict__


@billing_router.get("/usage")
async def list_usage(ctx: AuthContext = Depends(require_workspace)):
    return [u.__dict__ for u in get_stripe().get_usage(str(ctx.workspace.id))]


@billing_router.post("/portal")
async def billing_portal(ctx: AuthContext = Depends(require_workspace)):
    return get_stripe().create_portal_session(str(ctx.workspace.id))


# ---- 6.7 Slack + GitHub ---------------------------------------------------


@integrations_router.post("/slack/notify")
async def slack_notify(
    body: dict,
    ctx: AuthContext = Depends(require_workspace),
):
    channel = (body.get("channel") or "#general").strip()
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    msg = get_slack().post_message(
        workspace_id=str(ctx.workspace.id), channel=channel, text=text
    )
    return {"channel": msg.channel, "text": msg.text, "stub": True}


@integrations_router.post("/github/issues")
async def github_open_issue(
    body: dict,
    ctx: AuthContext = Depends(require_workspace),
):
    repo = (body.get("repo") or "").strip()
    title = (body.get("title") or "").strip()
    issue_body = (body.get("body") or "").strip()
    if not (repo and title):
        raise HTTPException(status_code=400, detail="repo and title are required")
    issue = get_github().open_issue(
        workspace_id=str(ctx.workspace.id), repo=repo, title=title, body=issue_body
    )
    return {
        "repo": issue.repo,
        "number": issue.number,
        "title": issue.title,
        "stub": True,
    }


@integrations_router.get("/github/issues")
async def github_list_issues(ctx: AuthContext = Depends(require_workspace)):
    return [
        {"repo": i.repo, "number": i.number, "title": i.title}
        for i in get_github().list_issues(str(ctx.workspace.id))
    ]


# ---- 6.8 Logto OAuth ------------------------------------------------------


@integrations_router.post("/logto/validate")
async def logto_validate(
    body: dict,
    _: AuthContext = Depends(require_workspace),
):
    """Verify a Logto-issued JWT (stubbed today).

    Requires DClaw auth: this endpoint is for an authenticated user to
    confirm that an external token they were just issued is still valid
    — NOT for anonymous identity probing.
    """
    token = (body.get("token") or "").strip()
    user = get_logto().validate(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid Logto token")
    return user.__dict__


# ---- 6.9 Document upload + summary ---------------------------------------


# Hard cap on a single upload (10 MiB by default). Override via the
# DCLAW_DOC_MAX_BYTES env var. We enforce streaming-style so a malicious
# upload doesn't materialize 10 GB into RAM before we notice the size.
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _docs_dir() -> Path:
    base = Path(os.environ.get("DCLAW_DOCS_DIR", "./uploads"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _max_upload_bytes() -> int:
    raw = os.environ.get("DCLAW_DOC_MAX_BYTES")
    if not raw:
        return DEFAULT_MAX_UPLOAD_BYTES
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_MAX_UPLOAD_BYTES


async def _read_with_cap(upload: UploadFile, cap: int) -> bytes:
    """Stream the upload in chunks and abort as soon as we exceed `cap`."""
    buf = bytearray()
    chunk_size = 64 * 1024
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > cap:
            raise HTTPException(
                status_code=413,
                detail=f"Upload exceeds the {cap} byte limit",
            )
    return bytes(buf)


class DocumentRead(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID | None
    filename: str
    content_type: str
    size_bytes: int
    summary: str | None

    model_config = ConfigDict(from_attributes=True)


@documents_router.post(
    "/", response_model=DocumentRead, status_code=status.HTTP_201_CREATED
)
async def upload_document(
    project_id: UUID | None = Form(default=None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    if project_id:
        await _project_or_404(db, project_id, ctx)
    raw = await _read_with_cap(file, _max_upload_bytes())
    safe_name = f"{uuid.uuid4().hex}-{Path(file.filename or 'upload').name}"
    path = _docs_dir() / safe_name
    path.write_bytes(raw)

    # Cheap summarization: pass first 4000 bytes of decoded text to the
    # Copilot. We tolerate undecodable bytes (binary uploads) by returning
    # None instead of trying to send them to the LLM.
    summary: str | None = None
    if file.content_type and file.content_type.startswith("text/"):
        text = raw[:4000].decode("utf-8", errors="ignore")
        if text.strip():
            result = await get_copilot().chat(
                [
                    ChatMessage(role="system", content="Summarize concisely in 3 sentences."),
                    ChatMessage(role="user", content=text),
                ],
                max_tokens=200,
            )
            summary = result.text

    doc = Document(
        workspace_id=ctx.workspace.id,
        project_id=project_id,
        filename=file.filename or safe_name,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(raw),
        storage_path=str(path),
        summary=summary,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@documents_router.get("/", response_model=list[DocumentRead])
async def list_documents(
    project_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    stmt = select(Document).where(Document.workspace_id == ctx.workspace.id)
    if project_id:
        await _project_or_404(db, project_id, ctx)
        stmt = stmt.where(Document.project_id == project_id)
    rows = await db.execute(stmt.order_by(Document.created_at.desc()))
    return list(rows.scalars().all())


# ---- 6.10 Sprints ---------------------------------------------------------


class SprintCreate(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date
    capacity_hours: int = Field(default=80, ge=1, le=4000)


class SprintRead(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    start_date: date
    end_date: date
    capacity_hours: int

    model_config = ConfigDict(from_attributes=True)


class SprintTaskAdd(BaseModel):
    task_ids: list[UUID] = Field(min_length=1)


class SprintWithTasks(SprintRead):
    task_ids: list[UUID]


@sprints_router.post(
    "/", response_model=SprintRead, status_code=status.HTTP_201_CREATED
)
async def create_sprint(
    body: SprintCreate,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    if body.end_date <= body.start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")
    await _project_or_404(db, body.project_id, ctx)
    sprint = Sprint(**body.model_dump())
    db.add(sprint)
    await db.commit()
    await db.refresh(sprint)
    return sprint


@sprints_router.get("/", response_model=list[SprintRead])
async def list_sprints(
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    await _project_or_404(db, project_id, ctx)
    rows = await db.execute(
        select(Sprint)
        .where(Sprint.project_id == project_id)
        .order_by(Sprint.start_date.desc())
    )
    return list(rows.scalars().all())


@sprints_router.post(
    "/{sprint_id}/tasks", response_model=SprintWithTasks
)
async def add_sprint_tasks(
    sprint_id: UUID,
    body: SprintTaskAdd,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    sprint = (await db.execute(select(Sprint).where(Sprint.id == sprint_id))).scalar_one_or_none()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    await _project_or_404(db, sprint.project_id, ctx)
    # Validate each task is in this project + workspace
    tasks = await TaskRepository(db).get_many(body.task_ids)
    if {t.id for t in tasks} != set(body.task_ids):
        raise HTTPException(status_code=404, detail="Some tasks not found")
    for t in tasks:
        if t.project_id != sprint.project_id:
            raise HTTPException(
                status_code=400,
                detail="All tasks must belong to the sprint's project",
            )
    existing_rows = await db.execute(
        select(SprintTask.task_id).where(SprintTask.sprint_id == sprint_id)
    )
    existing = {r[0] for r in existing_rows.all()}
    for tid in body.task_ids:
        if tid not in existing:
            db.add(SprintTask(sprint_id=sprint_id, task_id=tid))
    await db.commit()

    final_rows = await db.execute(
        select(SprintTask.task_id).where(SprintTask.sprint_id == sprint_id)
    )
    return SprintWithTasks(
        id=sprint.id,
        project_id=sprint.project_id,
        name=sprint.name,
        start_date=sprint.start_date,
        end_date=sprint.end_date,
        capacity_hours=sprint.capacity_hours,
        task_ids=[r[0] for r in final_rows.all()],
    )


@sprints_router.get("/{sprint_id}", response_model=SprintWithTasks)
async def get_sprint(
    sprint_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    sprint = (await db.execute(select(Sprint).where(Sprint.id == sprint_id))).scalar_one_or_none()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    await _project_or_404(db, sprint.project_id, ctx)
    task_rows = await db.execute(
        select(SprintTask.task_id).where(SprintTask.sprint_id == sprint_id)
    )
    return SprintWithTasks(
        id=sprint.id,
        project_id=sprint.project_id,
        name=sprint.name,
        start_date=sprint.start_date,
        end_date=sprint.end_date,
        capacity_hours=sprint.capacity_hours,
        task_ids=[r[0] for r in task_rows.all()],
    )


@sprints_router.delete(
    "/{sprint_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_sprint(
    sprint_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    sprint = (await db.execute(select(Sprint).where(Sprint.id == sprint_id))).scalar_one_or_none()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    await _project_or_404(db, sprint.project_id, ctx)
    await db.delete(sprint)
    await db.commit()
    return None
