from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.project_repo import ProjectRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.milestone_repo import MilestoneRepository
from app.services.ai_copilot import (
    ChatMessage,
    SYSTEM_PROMPT,
    get_copilot,
    project_context_block,
)
from app.services.project_health import compute_health
from app.services.wbs_generator import (
    WBSGenerator,
    WBSRequest,
    milestone_target_date,
)
from app.models.task import Task, TaskPriority
from app.models.milestone import Milestone

router = APIRouter()


# ---- Copilot chat ----------------------------------------------------------


class ChatRequestMessage(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = Field(min_length=1)


class CopilotChatRequest(BaseModel):
    messages: list[ChatRequestMessage] = Field(min_length=1)
    project_id: UUID | None = None


class CopilotChatResponse(BaseModel):
    text: str
    provider: str
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None


async def _project_context(db: AsyncSession, project_id: UUID) -> str:
    project = await ProjectRepository(db).get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    data = {
        "name": project.name,
        "status": project.status.value,
        "owner": project.owner,
        "description": project.description,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "end_date": project.end_date.isoformat() if project.end_date else None,
        "tasks": [
            {
                "title": t.title,
                "status": t.status.value,
                "priority": t.priority.value,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "assignee": t.assignee,
            }
            for t in project.active_tasks
        ],
        "milestones": [
            {
                "name": m.name,
                "target_date": m.target_date.isoformat(),
                "completed": m.completed,
            }
            for m in project.active_milestones
        ],
    }
    return project_context_block(data)


@router.post("/copilot/chat", response_model=CopilotChatResponse)
async def copilot_chat(
    body: CopilotChatRequest, db: AsyncSession = Depends(get_db)
):
    copilot = get_copilot()
    messages: list[ChatMessage] = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
    if body.project_id:
        context = await _project_context(db, body.project_id)
        messages.append(
            ChatMessage(role="system", content="Project context:\n" + context)
        )
    messages.extend(ChatMessage(role=m.role, content=m.content) for m in body.messages)
    result = await copilot.chat(messages, max_tokens=600)
    return CopilotChatResponse(
        text=result.text,
        provider=result.provider,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
    )


# ---- Project health --------------------------------------------------------


class HealthSignalRead(BaseModel):
    label: str
    weight: float
    penalty: float


class ProjectHealthResponse(BaseModel):
    project_id: UUID
    score: int
    status: str
    narrative: str
    signals: list[HealthSignalRead]
    top_risks: list[str]


@router.get("/projects/{project_id}/health", response_model=ProjectHealthResponse)
async def project_health(project_id: UUID, db: AsyncSession = Depends(get_db)):
    project = await ProjectRepository(db).get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    report = compute_health(project)
    return ProjectHealthResponse(
        project_id=project_id,
        score=report.score,
        status=report.status,
        narrative=report.narrative,
        signals=[
            HealthSignalRead(
                label=s.label, weight=s.weight, penalty=round(s.penalty, 3)
            )
            for s in report.signals
        ],
        top_risks=report.top_risks,
    )


# ---- WBS generator ---------------------------------------------------------


class GenerateWBSRequest(BaseModel):
    goal: str = Field(min_length=3)
    deadline_days: int = Field(default=30, ge=1, le=365)
    team_size: int = Field(default=3, ge=1, le=100)
    project_id: UUID | None = None  # if provided, materialize into this project
    project_name: str | None = Field(default=None, min_length=1, max_length=255)
    owner: str | None = Field(default=None, min_length=1, max_length=255)


class GeneratedTaskOut(BaseModel):
    title: str
    description: str
    priority: str
    estimated_hours: int
    depends_on: list[int]


class GeneratedMilestoneOut(BaseModel):
    name: str
    target_offset_days: int
    target_date: date


class GenerateWBSResponse(BaseModel):
    project_id: UUID
    tasks: list[GeneratedTaskOut]
    milestones: list[GeneratedMilestoneOut]
    provider: str
    model: str
    created_task_ids: list[UUID]
    created_milestone_ids: list[UUID]


@router.post("/generate-wbs", response_model=GenerateWBSResponse)
async def generate_wbs(body: GenerateWBSRequest, db: AsyncSession = Depends(get_db)):
    from app.models.project import Project

    project_repo = ProjectRepository(db)
    existing_project_id = body.project_id
    if existing_project_id:
        project = await project_repo.get_by_id(existing_project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    else:
        if not body.project_name or not body.owner:
            raise HTTPException(
                status_code=400,
                detail="When project_id is not provided, project_name and owner are required.",
            )
        project = None  # created inside the transaction below

    generator = WBSGenerator()
    result = await generator.generate(
        WBSRequest(
            goal=body.goal,
            deadline_days=body.deadline_days,
            team_size=body.team_size,
        )
    )

    # Single atomic write: project (if new) + tasks (with parent FKs from
    # depends_on[0]) + milestones, one commit. On any failure the new
    # project does not survive.
    created_tasks: list[Task] = []
    created_milestones: list[Milestone] = []
    try:
        if project is None:
            project = Project(name=body.project_name, owner=body.owner)
            db.add(project)
            await db.flush()  # populate project.id without committing

        # First pass: stage tasks without parent FKs so we get IDs.
        for gt in result.tasks:
            task = Task(
                project_id=project.id,
                title=gt.title,
                description=gt.description,
                priority=TaskPriority(gt.priority),
                estimated_hours=gt.estimated_hours,
            )
            db.add(task)
            created_tasks.append(task)
        await db.flush()  # populate task IDs

        # Second pass: wire depends_on[0] (the primary prerequisite) into
        # parent_task_id. We only consume the first dep because the schema
        # only models one parent edge; the rest are returned in the response
        # for the UI to render but are not persisted as FKs.
        for gt, task in zip(result.tasks, created_tasks):
            if not gt.depends_on:
                continue
            for idx in gt.depends_on:
                if 0 <= idx < len(created_tasks) and created_tasks[idx].id != task.id:
                    task.parent_task_id = created_tasks[idx].id
                    break

        for gm in result.milestones:
            m = Milestone(
                project_id=project.id,
                name=gm.name,
                target_date=milestone_target_date(gm.target_offset_days),
            )
            db.add(m)
            created_milestones.append(m)

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    for t in created_tasks:
        await db.refresh(t)
    for m in created_milestones:
        await db.refresh(m)

    return GenerateWBSResponse(
        project_id=project.id,
        tasks=[
            GeneratedTaskOut(
                title=gt.title,
                description=gt.description,
                priority=gt.priority,
                estimated_hours=gt.estimated_hours,
                depends_on=gt.depends_on,
            )
            for gt in result.tasks
        ],
        milestones=[
            GeneratedMilestoneOut(
                name=gm.name,
                target_offset_days=gm.target_offset_days,
                target_date=milestone_target_date(gm.target_offset_days),
            )
            for gm in result.milestones
        ],
        provider=result.provider,
        model=result.model,
        created_task_ids=[t.id for t in created_tasks],
        created_milestone_ids=[m.id for m in created_milestones],
    )
