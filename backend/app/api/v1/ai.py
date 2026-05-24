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
            for t in project.tasks
            if t.deleted_at is None
        ],
        "milestones": [
            {
                "name": m.name,
                "target_date": m.target_date.isoformat(),
                "completed": m.completed,
            }
            for m in project.milestones
            if m.deleted_at is None
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
    project_repo = ProjectRepository(db)
    if body.project_id:
        project = await project_repo.get_by_id(body.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    else:
        if not body.project_name or not body.owner:
            raise HTTPException(
                status_code=400,
                detail="When project_id is not provided, project_name and owner are required.",
            )
        from app.models.project import Project

        project = Project(name=body.project_name, owner=body.owner)
        project = await project_repo.create(project)

    generator = WBSGenerator()
    result = await generator.generate(
        WBSRequest(
            goal=body.goal,
            deadline_days=body.deadline_days,
            team_size=body.team_size,
        )
    )

    task_repo = TaskRepository(db)
    milestone_repo = MilestoneRepository(db)

    created_tasks: list[Task] = []
    for gt in result.tasks:
        task = Task(
            project_id=project.id,
            title=gt.title,
            description=gt.description,
            priority=TaskPriority(gt.priority),
            estimated_hours=gt.estimated_hours,
        )
        await task_repo.create(task)
        created_tasks.append(task)

    created_milestones: list[Milestone] = []
    for gm in result.milestones:
        target = milestone_target_date(gm.target_offset_days)
        m = Milestone(
            project_id=project.id,
            name=gm.name,
            target_date=target,
        )
        await milestone_repo.create(m)
        created_milestones.append(m)

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
