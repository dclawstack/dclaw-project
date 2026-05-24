# DClaw Assets

> AI-assisted asset management — a DClaw vertical SaaS app.

`dclaw-assets` is the asset-tracking app in the DClaw stack. Track assets, owners, lifecycle, and value, with an AI copilot for classification, depreciation forecasting, and renewal/replacement suggestions.

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14 (App Router), Tailwind CSS, pre-built UI components |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), asyncpg |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| Tests | pytest + `pytest-asyncio==0.24.0` |
| Container | Docker + docker-compose; Helm chart for K8s |
| CI | GitHub Actions (`.github/workflows/ci.yml`) |

## Ports & Database

Authoritative source: [`AGENTS.md`](./AGENTS.md).

| Service | Port | Where it's defined |
|---------|------|--------------------|
| Backend (FastAPI) | **8100** | `backend/Dockerfile` (`ENV PORT`, `EXPOSE`, `CMD`), `docker-compose.yml` |
| Frontend (Next.js) | **3010** | `frontend/Dockerfile` (`ENV PORT`, `EXPOSE`), `docker-compose.yml` |
| PostgreSQL | **5432** | `docker-compose.yml`, `backend/tests/conftest.py` (CI requirement) |
| Database name | `dclaw_assets` | `backend/app/core/config.py`, `docker-compose.yml`, `.env.example` |
| Base API path | `/api/v1` | `backend/app/api/main.py` |

## Local Development

```bash
# 1. Copy env and edit if needed
cp .env.example .env

# 2. Bring up the stack
docker compose up -d --build

# 3. Apply migrations
docker compose exec backend alembic upgrade head

# 4. Open the app
# Frontend: http://localhost:3010
# Backend:  http://localhost:8100/health/
# API docs: http://localhost:8100/docs
```

### Running tests

```bash
cd backend
pytest -v
```

CI uses a Postgres service mapped to `localhost:5432` with database `dclaw_assets_test` — do not change that mapping.

## Project Layout

```
dclaw-project/
├── backend/                  # FastAPI app
│   ├── app/
│   │   ├── api/              # Routes (health, v1: projects, tasks, milestones)
│   │   ├── core/             # config, database
│   │   ├── models/           # SQLAlchemy 2.0 models
│   │   ├── repositories/     # CRUD layer
│   │   ├── schemas/          # Pydantic v2
│   │   └── services/         # Business logic / AI
│   ├── alembic/              # Migrations
│   └── tests/
├── frontend/                 # Next.js 14 (App Router)
│   └── src/
│       ├── app/              # Pages
│       ├── components/ui/    # Pre-built UI primitives — do NOT install shadcn CLI
│       └── lib/              # api.ts client, utils
├── helm/                     # K8s chart (dclaw-assets)
├── docker-compose.yml
├── .github/workflows/ci.yml
├── AGENTS.md                 # Architecture lock — read before changing code
├── REVISED-PRD.md            # Product requirements
└── PLAN-v1.2.md              # Feature backlog
```

## Critical Rules

These come straight from `AGENTS.md`. Read that file before touching code.

- **Do NOT install the shadcn CLI** — use the pre-built components in `frontend/src/components/ui/`.
- **Do NOT change the Postgres test port** — `backend/tests/conftest.py` must use `localhost:5432`; CI maps it there.
- **Do NOT delete `.github/workflows/ci.yml`**.
- **Do NOT upgrade `pytest-asyncio`** beyond `0.24.0` — v1.x breaks fixture scoping.
- **All DB access** goes through `app/repositories/`; no in-memory mocks.
- **New models** require an Alembic migration.

## Contributors

| Name | Email |
|------|-------|
| Rajendra Machani | 01.r.machani@gmail.com |
