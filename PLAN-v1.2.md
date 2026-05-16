# CRM — v1.2 Feature Roadmap

> 📘 **REVISED PRD v2.3 available:** See `REVISED-PRD.md` for complete gap analysis, current state, and full feature roadmap.


> **For coding agents:** Pick features from this list, implement them fully, and update this doc with a checkmark.
> **Do NOT change the basic stack.** See `AGENTS.md` for architecture lock.

## Pre-Flight Checklist — Do This First

Before implementing any v1.2 feature, verify:

- [ ] `frontend/package-lock.json` is committed after any `npm install` / dependency change
- [ ] `frontend/next-env.d.ts` exists and is committed (required for Next.js TypeScript builds)
- [ ] `frontend/.gitignore` excludes `node_modules/` and `.next/`
- [ ] `docker-compose.yml` healthchecks use `python urllib.request.urlopen()` (backend) and `wget -q --spider` (frontend)
- [ ] `frontend/Dockerfile` declares `ARG NEXT_PUBLIC_API_URL` before `RUN npm run build`

## v1.0 Feature Inventory (Current)

- [ ] Core entity CRUD (TODO: list your entities)
- [ ] Dashboard / main page
- [ ] Real backend CRUD (no mocks)
- [ ] Docker + Helm deployment
- [ ] Alembic migrations
- [ ] Backend tests

---

## v1.2 Roadmap

### P0 — Must Have

#### 1. Feature Name
**Description:** What it does.
- **Backend:** What to build.
- **Frontend:** What to build.
- **Files to touch:** `backend/app/...`, `frontend/src/...`

### P1 — Should Have

#### 2. Feature Name
**Description:** What it does.
- **Backend:** What to build.
- **Frontend:** What to build.

### P2 — Could Have

#### 3. Feature Name
**Description:** What it does.

---

## Implementation Priority

1. (Fill in)
