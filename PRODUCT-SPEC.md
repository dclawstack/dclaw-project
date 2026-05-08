# PRODUCT-SPEC: Project

## Overview

**App Name:** Project
**Domain:** Task management, Gantt charts, team collaboration
**Target User:** Project managers, team leads, developers

## Core Entities

### Project
```
Project
├── id: UUID (PK)
├── name: str (required)
├── description: str (optional)
├── status: enum ["planning", "active", "on_hold", "completed", "cancelled"] (default: "planning")
├── start_date: date (optional)
├── end_date: date (optional)
├── owner: str (required)
├── created_at: datetime
└── updated_at: datetime
```

### Task
```
Task
├── id: UUID (PK)
├── project_id: UUID (FK → Project, ondelete=CASCADE)
├── title: str (required)
├── description: str (optional)
├── status: enum ["todo", "in_progress", "review", "done"] (default: "todo")
├── priority: enum ["low", "medium", "high", "urgent"] (default: "medium")
├── assignee: str (optional)
├── due_date: date (optional)
├── created_at: datetime
└── updated_at: datetime
```

### Milestone
```
Milestone
├── id: UUID (PK)
├── project_id: UUID (FK → Project, ondelete=CASCADE)
├── name: str (required)
├── description: str (optional)
├── target_date: date (required)
├── completed: bool (default false)
├── created_at: datetime
└── updated_at: datetime
```

## User Stories / Screens

### Screen 1: Dashboard
- Summary cards: active projects, tasks due today, completed tasks, overdue tasks
- Projects by status pie chart (mock)
- Recent tasks list

### Screen 2: Projects
- Card grid showing project name, status, progress bar, date range
- Status filter
- "Add Project" form

### Screen 3: Project Detail
- Project info with edit/delete
- Task board (Kanban: todo → in_progress → review → done)
- Milestones list with progress
- "Add Task" and "Add Milestone" buttons

### Screen 4: Task Detail
- Task info with status dropdown, priority selector, assignee input
- Edit / delete
- Due date display

## AI Features

- **Task estimation:** Suggest task duration based on title and description (mock)
- **Risk flag:** Flag tasks at risk of missing deadline (mock)

## API Endpoints (v1.0)

```
GET    /api/v1/projects           → List projects
POST   /api/v1/projects           → Create project
GET    /api/v1/projects/{id}      → Get project
PUT    /api/v1/projects/{id}      → Update project
DELETE /api/v1/projects/{id}      → Delete project
GET    /api/v1/tasks              → List tasks
POST   /api/v1/tasks              → Create task
GET    /api/v1/tasks/{id}         → Get task
PUT    /api/v1/tasks/{id}         → Update task
DELETE /api/v1/tasks/{id}         → Delete task
GET    /api/v1/milestones         → List milestones
POST   /api/v1/milestones         → Create milestone
GET    /api/v1/milestones/{id}    → Get milestone
PUT    /api/v1/milestones/{id}    → Update milestone
DELETE /api/v1/milestones/{id}    → Delete milestone
GET    /api/v1/dashboard          → Dashboard stats
```

## Non-Functional Requirements

- Backend tests: 70%+ coverage
- Frontend: Responsive, Tailwind + pre-built UI components
- Docker: All services start with `docker compose up -d`
- No mock data — everything persisted to PostgreSQL
