# DClaw Project — v1.2 YC-Grade Feature Roadmap

> **YC submission positioning:** *The autonomous project manager that prevents the 70% of projects that fail.*
> Every feature below is rationalized against YC reviewer criteria: hair-on-fire problem, technical depth, defensibility, and scale.
>
> See `REVISED-PRD.md` for product vision and `AGENTS.md` for architecture lock.

---

## 0. YC Evaluation Summary

### 0.1 What we are building
DClaw Project is an AI-native project management platform where autonomous LLM agents continuously plan, monitor, predict, and reroute work — turning the project manager from a clerk into a strategist.

### 0.2 Hair-on-fire problem
- 70% of all projects miss scope, budget, or deadline (Standish CHAOS Report).
- PMs spend 40–60% of their time on status updates, scheduling, and admin instead of unblocking work.
- Risks are visible 2–4 weeks before deadline slip — but no tool detects them automatically.
- Existing tools (Asana, Jira, Monday, Linear) are *databases with kanban boards*. None of them think.

### 0.3 Why this is a YC-grade opportunity
| YC criterion | DClaw Project answer |
|--------------|----------------------|
| **10× improvement** | Generate a full WBS in 90 seconds vs 2 weeks; predict slip 2 weeks early; auto-reassign blocked tasks |
| **Defensibility** | Proprietary project-graph + outcome dataset; the more projects you run the better the risk model gets |
| **Technical depth** | Agentic LLM workflows, RAG over project memory, critical-path solver, constraint-based resource leveling |
| **Wedge** | Hybrid local-first (Ollama) + cloud LLMs → enterprise-friendly; on-prem deployable from day one |
| **Distribution** | DPanel embedding + Slack / GitHub / Calendar integrations + native CLI for engineering teams |

### 0.4 Gaps vs YC bar (and how this roadmap closes them)
1. **No AI Copilot yet** → Complexity-1 features 1.1, 1.2, 1.3 ship it.
2. **No defensible moat** → Complexity-2 features 2.1, 2.2, 2.5 build the agent + memory + risk-model moat.
3. **Single-tenant, no auth** → Complexity-1 feature 1.10 adds workspaces and RBAC.
4. **No real-time collaboration** → Complexity-1 feature 1.7 adds SSE-based live updates.
5. **No automation/orchestration** → Complexity-2 feature 2.1 introduces agent workflows.
6. **No integrations / distribution surface** → Complexity-2 features 2.7, 2.8, 2.9 attach the platform.
7. **No metrics / observability for product itself** → Complexity-0 feature 0.7 adds structured logging.
8. **No analytics / unit economics signal for YC** → Complexity-1 feature 1.4 (health score) + 1.5 (velocity) generate the KPI surface.

---

## 1. Pre-Flight Checklist — Do This First

- [x] `frontend/package-lock.json` is committed
- [x] `frontend/next-env.d.ts` exists and is committed
- [x] `frontend/.gitignore` excludes `node_modules/` and `.next/`
- [x] `docker-compose.yml` healthchecks use `python urllib.request.urlopen()` (backend) and `wget -q --spider` (frontend)
- [x] `frontend/Dockerfile` declares `ARG NEXT_PUBLIC_API_URL` before `RUN npm run build`
- [x] Local SQLite dev DB available for non-Docker workflows (`DATABASE_URL=sqlite+aiosqlite:///./dclaw_project.db`)

---

## 2. v1.0 Feature Inventory (Already Implemented)

- [x] Project / Task / Milestone CRUD
- [x] Project detail with embedded tasks + milestones
- [x] Dashboard with due-today / overdue / completed counters
- [x] Projects list with status filter
- [x] Async FastAPI + SQLAlchemy 2.0 repository pattern
- [x] Next.js 14 App Router frontend with custom UI library
- [x] Docker compose + Helm chart
- [x] Alembic scaffolding
- [x] Backend pytest suite for CRUD endpoints

---

## 3. Roadmap — Complexity-Based Numbering

Each feature is tagged `[C0]`, `[C1]`, or `[C2]`:
- **C0** Low complexity, foundational, ship same day
- **C1** Core differentiators that prove the "AI-native" thesis
- **C2** High-complexity moats (agentic AI, optimization, integrations)

---

## 4. C0 — Foundational Quick Wins  (ship in v1.2.0)

### 4.0 [C0] Local SQLite dev database
**Why:** Frictionless `python -m uvicorn` without Docker; lowers contributor onboarding from 10 min to 30 sec.
- **Backend:** Auto-detect `sqlite+aiosqlite://` URL in `core/database.py`, drop pool args that PG-only.
- **Schema:** `dclaw_project.db` SQLite file initialized on lifespan startup via `Base.metadata.create_all` when running outside production.
- **Files:** `backend/app/core/database.py`, `backend/app/core/config.py`, `backend/requirements.txt`, `.env.example`.

### 4.1 [C0] Timestamped + soft-deletable models
**Why:** Every YC reviewer expects audit trails; soft-delete enables undo + retention.
- **Backend:** `TimestampMixin` (`created_at`, `updated_at`), `SoftDeleteMixin` (`deleted_at`).
- **Migration:** Alembic revision adding columns + indexes.
- **Files:** `backend/app/models/mixins.py`, all model files.

### 4.2 [C0] Tags / labels for projects and tasks
**Why:** Foundation for filtering, search, and downstream AI prompts.
- **Backend:** `Tag` model + many-to-many association tables.
- **API:** `/api/v1/tags` CRUD + tag attachment endpoints.
- **Files:** `backend/app/models/tag.py`, `schemas/tag.py`, `repositories/tag_repo.py`, `api/v1/tags.py`.

### 4.3 [C0] Comments on tasks (activity stream)
**Why:** Collaboration table stakes + future-proof for AI summary generation.
- **Backend:** `Comment` model with author + body + task FK.
- **API:** Nested under `/api/v1/tasks/{id}/comments`.
- **Files:** `backend/app/models/comment.py`, `schemas/comment.py`, `repositories/comment_repo.py`, `api/v1/comments.py`.

### 4.4 [C0] Subtasks (self-referencing parent_id on Task)
**Why:** PRD acceptance: "Unlimited nesting; milestones; burndown charts".
- **Backend:** Nullable `parent_task_id` FK on Task + cycle-prevention check.
- **API:** `/api/v1/tasks/{id}/subtasks`.
- **Files:** `backend/app/models/task.py`, `repositories/task_repo.py`.

### 4.5 [C0] Server-side search / filtering / pagination
**Why:** A real product cannot return `limit=1000`. Pagination is a YC code-quality smell test.
- **Backend:** Query params `q`, `status`, `priority`, `assignee`, `tag`, `limit`, `offset` on tasks & projects.
- **Response:** `{items, total, limit, offset}`.
- **Files:** `backend/app/api/v1/projects.py`, `tasks.py`, repos.

### 4.6 [C0] Bulk task operations
**Why:** Reviewers expect modern UX; bulk status change is a 10× workflow.
- **API:** `POST /api/v1/tasks/bulk` with `{ids, patch}` payload.
- **Files:** `backend/app/api/v1/tasks.py`.

### 4.7 [C0] Structured logging + request IDs
**Why:** Observability proves the team thinks about production.
- **Backend:** `structlog` + request-id middleware + uvicorn log integration.
- **Files:** `backend/app/core/logging.py`, `app/api/main.py`.

### 4.8 [C0] OpenAPI metadata polish + healthz with DB ping
**Why:** First impression in `/docs`; ops-readiness for Helm.
- **Backend:** Tags, descriptions, examples; `/health/ready` runs a `SELECT 1`.
- **Files:** `backend/app/api/main.py`, `app/api/routes/health.py`.

### 4.9 [C0] Tasks endpoint: stats by project
**Why:** Powers project-detail burndown and dashboard.
- **API:** `/api/v1/projects/{id}/stats` returns `{total, by_status, by_priority, completion_pct}`.
- **Files:** `backend/app/api/v1/projects.py`, `repositories/task_repo.py`.

### 4.10 [C0] Frontend: task creation modal, inline edit, dashboard polish
**Why:** Self-evident product story for YC demo video.
- **Frontend:** `New Task` dialog on project detail, edit dialogs, badge color system, empty states.
- **Files:** `frontend/src/app/projects/[id]/page.tsx`, `app/tasks/[id]/page.tsx`.

---

## 5. C1 — Core Differentiators  (v1.2.x — proves the AI thesis)

### 5.1 [C1] AI Copilot API + Floating Chat UI
**Why:** PRD §9 mandates it; it is the *headline* P0 feature.
- **Backend service:** `services/ai_copilot.py` calling OpenRouter cloud → falling back to local Ollama; streaming via SSE.
- **API:** `POST /api/v1/ai/copilot/chat` (streaming) + `/api/v1/ai/copilot/suggest-next-actions`.
- **Context:** Inject project state, task list, blockers as system prompt.
- **Frontend:** Floating chat widget reachable from every page; markdown rendering; thinking indicator.
- **Files:** `backend/app/services/ai_copilot.py`, `app/api/v1/ai.py`, `frontend/src/components/copilot/*`.

### 5.2 [C1] AI-generated Work Breakdown Structure (WBS)
**Why:** PRD acceptance: "Generate WBS in <2min". This is the *wow* feature.
- **Backend:** `POST /api/v1/ai/generate-wbs` taking `{project_goal, deadline, team_size}` → returns structured task tree.
- **Implementation:** Few-shot prompt template → JSON mode → server-side validation → persisted tasks/milestones in one transaction.
- **Frontend:** "✨ Generate plan" button on new project flow.

### 5.3 [C1] Kanban board view per project
**Why:** Modern PM table-stakes; visual proof of polish.
- **Frontend:** Drag-and-drop columns (`todo / in_progress / review / done`); HTML5 DnD, optimistic update + rollback on API failure.
- **Backend:** `PATCH /api/v1/tasks/{id}/status` already covered by existing PUT.

### 5.4 [C1] Project health score + RAG-style risk feed
**Why:** PRD acceptance: "Predict delays; suggest reallocations". Highest-signal demo metric.
- **Backend:** Rule-based + LLM hybrid: `services/project_health.py` computes a 0–100 score from: % overdue, slack, milestone proximity, comment sentiment, velocity trend. LLM produces a one-paragraph "executive narrative".
- **API:** `GET /api/v1/projects/{id}/health`.
- **Frontend:** Health gauge + narrative card on project detail.

### 5.5 [C1] Burndown + velocity charts
**Why:** Same data, two charts, immediate analytics depth.
- **Backend:** `GET /api/v1/projects/{id}/burndown` returning daily remaining / completed series; reuses task completion timestamps.
- **Frontend:** Pure-SVG line chart (no chart library to keep bundle small).

### 5.6 [C1] Time tracking
**Why:** P1.1 in PRD; opens billable / margin features.
- **Backend:** `TimeEntry` model (task_id, user, start, end, duration_seconds, billable).
- **API:** `/api/v1/time-entries` CRUD + `/start`, `/stop`.
- **Frontend:** Timer on task detail.

### 5.7 [C1] Real-time updates via Server-Sent Events
**Why:** Live PM tool. Distinguishes us from polling-based competitors.
- **Backend:** In-process pub/sub (`asyncio.Queue` per workspace) → `/api/v1/events/stream`.
- **Frontend:** `EventSource` hook driving SWR-style cache invalidation.

### 5.8 [C1] Task dependencies (FS, SS, FF, SF)
**Why:** PRD acceptance: "4 dependency types; resource leveling".
- **Backend:** `TaskDependency` association with type enum; cycle check via DFS on insert.
- **API:** `POST /api/v1/tasks/{id}/dependencies`, `DELETE /api/v1/dependencies/{id}`.

### 5.9 [C1] In-app notifications + unread badge
**Why:** Stickiness; also feeds the AI Copilot (it can surface critical alerts).
- **Backend:** `Notification` model; emitter on status changes, mentions, due-soon.
- **API:** `/api/v1/notifications` + mark-read endpoints.

### 5.10 [C1] Workspaces + simple JWT auth + RBAC
**Why:** Multi-tenant SaaS readiness; required for any monetization signal.
- **Backend:** `Workspace`, `User`, `WorkspaceMember(role)` models. JWT auth via `python-jose`. `get_current_user` dep injection.
- **Migration:** Add `workspace_id` FK to Project (default workspace seeded).
- **API:** `/api/v1/auth/register`, `/auth/login`, `/auth/me`.

---

## 6. C2 — High-Complexity Moats  (v1.3+)

### 6.1 [C2] Agentic project planner (multi-step LLM workflow)
**Why:** From "AI feature" to "AI product". Demonstrates technical depth for YC.
- **Backend:** State machine: `goal → research → wbs → estimate → critical-path → assignment → review`. Each step is a tool call; the agent loops with a 5-step budget.
- **Persistence:** `AgentRun` model storing trace + tokens.
- **API:** `POST /api/v1/ai/agent/plan` (long-running, SSE).
- **Telemetry:** `tokens_in`, `tokens_out`, `latency_ms` per step.

### 6.2 [C2] RAG over project knowledge base
**Why:** Each org's project history becomes the moat — embeddings of comments, task descriptions, decisions.
- **Backend:** `EmbeddingChunk(entity_type, entity_id, content, embedding)`; pgvector in prod, `sqlite-vec`/cosine fallback in dev.
- **Pipeline:** Async background job indexes new comments/tasks.
- **API:** `POST /api/v1/ai/search` semantic search; `/api/v1/ai/ask` answers with citations.

### 6.3 [C2] Critical path computation + Gantt UI
**Why:** PRD acceptance: "Critical-path optimization + buffer-suggestion".
- **Backend:** DAG + topological sort + earliest/latest start algorithm; `services/critical_path.py`.
- **API:** `GET /api/v1/projects/{id}/critical-path` returns ordered task chain + slack per task.
- **Frontend:** SVG Gantt chart with critical path highlighted.

### 6.4 [C2] Constraint-based resource leveling
**Why:** PRD acceptance: "optimize allocation; prevent overbooking".
- **Backend:** Greedy + back-tracking allocator that respects per-person capacity windows; later upgrade to OR-tools.
- **API:** `POST /api/v1/projects/{id}/optimize-resources` returns proposed reassignments.

### 6.5 [C2] Predictive risk model (delay forecasting)
**Why:** Defensible: training data accrues with every project we run.
- **Backend:** Feature pipeline (overdue %, velocity trend, dependency depth, team load) → logistic regression baseline → model server.
- **API:** `GET /api/v1/projects/{id}/risk-forecast` → `{p_slip_2w, p_slip_4w, top_factors}`.

### 6.6 [C2] Stripe metered billing
**Why:** Monetization signal for YC: "we charge per active project per month."
- **Backend:** Stripe webhook → usage events on project create / AI call.
- **API:** `/api/v1/billing/portal` for subscription management.

### 6.7 [C2] Slack + GitHub integrations
**Why:** Distribution; tasks created from Slack threads or GitHub issues.
- **Backend:** Webhook receivers + outbound notifiers; OAuth via Logto.

### 6.8 [C2] Logto OAuth (replacing local JWT)
**Why:** Enterprise-readiness for the YC interview.
- **Backend:** Validate Logto JWTs in middleware; map `sub` → User row.

### 6.9 [C2] Document upload + AI summarization
**Why:** PMs live in spec PDFs; ingest + summarize closes the loop.
- **Backend:** MinIO upload → background OCR/parse → embed → AI summary.

### 6.10 [C2] Sprint / scrum board with AI capacity planning
**Why:** P2.2 in PRD; serves engineering org buyer persona.
- **Backend:** `Sprint(start, end, capacity_points)`, `SprintTask(sprint_id, task_id)`.
- **API:** `/api/v1/sprints` CRUD + AI-suggested sprint backlog endpoint.

---

## 7. Implementation Priority Order

The implementation order this branch will follow:

1. **Round 1 — C0 quick wins (in order):** 4.0 → 4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6 → 4.7 → 4.8 → 4.9 → 4.10
2. **Round 2 — C1 essentials (AI-native thesis):** 5.1 → 5.2 → 5.4 → 5.3 → 5.5 → 5.8
3. **Round 3 — C1 platform:** 5.6 → 5.7 → 5.9 → 5.10
4. **Round 4 — C2 moats:** 6.1 → 6.2 → 6.3 → 6.5 → 6.4 → 6.10 → 6.6 → 6.7 → 6.8 → 6.9

Every feature must ship with tests where applicable and keep `pytest backend/tests` green.

---

## 8. Implementation Status (live)

### v1.2.0 — C0 + C1 wave 1 (merged in PR #2)

| # | Feature | Complexity | Status |
|---|---------|------------|--------|
| 4.0 | Local SQLite dev DB | C0 | ✅ |
| 4.1 | Timestamps + soft-delete | C0 | ✅ |
| 4.2 | Tags / labels | C0 | ✅ |
| 4.3 | Comments on tasks | C0 | ✅ |
| 4.4 | Subtasks | C0 | ✅ |
| 4.5 | Search / filter / pagination | C0 | ✅ |
| 4.6 | Bulk task ops | C0 | ✅ |
| 4.7 | Structured logging | C0 | ✅ |
| 4.8 | OpenAPI polish + ready probe | C0 | ✅ |
| 4.9 | Project stats endpoint | C0 | ✅ |
| 4.10 | Frontend task UX polish | C0 | ✅ |
| 5.1 | AI Copilot API + chat UI | C1 | ✅ |
| 5.2 | AI WBS generator | C1 | ✅ |
| 5.3 | Kanban board (read-only) | C1 | ✅ |
| 5.4 | Project health score | C1 | ✅ |

### v1.2.1 — C1 wave 2 + C2 (this branch)

| # | Feature | Complexity | Status |
|---|---------|------------|--------|
| 5.10 | Workspaces + JWT auth (full gating) | C1 | ✅ |
| 5.8 | Task dependencies (FS/SS/FF/SF) | C1 | ✅ |
| 5.5 | Burndown + velocity | C1 | ✅ |
| 5.6 | Time tracking | C1 | ✅ |
| 5.9 | Notifications | C1 | ✅ |
| 5.7 | SSE real-time | C1 | ✅ |
| 5.3+ | Kanban drag-and-drop | C1 | ✅ |
| 6.3 | Critical path (backend) | C2 | ✅ |
| 6.1 | Agentic planner (multi-step LLM) | C2 | ✅ |
| 6.5 | Predictive risk model | C2 | ✅ |
| 6.2 | RAG over project knowledge base | C2 | ✅ |
| 6.4 | Resource leveling | C2 | ✅ |
| 6.6 | Stripe billing (local stub) | C2 | ✅ |
| 6.7 | Slack + GitHub integrations (local stub) | C2 | ✅ |
| 6.8 | Logto OAuth (local stub) | C2 | ✅ |
| 6.9 | Document upload + AI summary (local FS) | C2 | ✅ |
| 6.10 | Sprint board | C2 | ✅ |

Implementation order this branch will follow:
1. **Auth foundation:** 5.10 first — every later route depends on it
2. **Task graph:** 5.8 (dependencies) → 6.3 (critical path) — algorithmic spine
3. **Activity surface:** 5.6 (time) → 5.5 (burndown) → 5.9 (notifications) → 5.7 (SSE)
4. **Frontend polish:** 5.3+ (kanban DnD)
5. **AI moats:** 6.1 (agent) → 6.5 (risk) → 6.2 (RAG) → 6.4 (leveling)
6. **Integration stubs:** 6.9 (docs/local FS) → 6.6 (Stripe) → 6.7 (Slack/GH) → 6.8 (Logto) → 6.10 (sprints)
