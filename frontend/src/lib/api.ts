const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const TOKEN_KEY = "dclaw_token";

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const response = await fetch(url, {
    ...options,
    headers,
  });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API error ${response.status}: ${error}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json();
}

export async function getHealth() {
  return fetchJson<{ status: string }>("/health/");
}

export type ProjectStatus = "planning" | "active" | "on_hold" | "completed" | "cancelled";
export type TaskStatus = "todo" | "in_progress" | "review" | "done";
export type TaskPriority = "low" | "medium" | "high" | "urgent";

export interface Tag {
  id: string;
  name: string;
  color: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  start_date: string | null;
  end_date: string | null;
  owner: string;
  created_at: string;
  updated_at: string;
  tags: Tag[];
}

export interface ProjectDetail extends Project {
  tasks: Task[];
  milestones: Milestone[];
}

export interface Task {
  id: string;
  project_id: string;
  parent_task_id: string | null;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  assignee: string | null;
  due_date: string | null;
  completed_at: string | null;
  estimated_hours: number | null;
  created_at: string;
  updated_at: string;
  tags: Tag[];
}

export interface Milestone {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  target_date: string;
  completed: boolean;
  created_at: string;
  updated_at: string;
}

export interface Comment {
  id: string;
  task_id: string;
  author: string;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ProjectStats {
  total_tasks: number;
  by_status: Record<TaskStatus, number>;
  by_priority: Record<TaskPriority, number>;
  completion_pct: number;
  overdue: number;
  due_soon: number;
  milestone_count: number;
  milestone_completed: number;
}

export interface ProjectListParams {
  q?: string;
  status?: ProjectStatus;
  owner?: string;
  tag?: string;
  limit?: number;
  offset?: number;
}

export interface TaskListParams {
  q?: string;
  project_id?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  assignee?: string;
  tag?: string;
  parent_task_id?: string;
  limit?: number;
  offset?: number;
}

function toQs(params: object | undefined): string {
  if (!params) return "";
  const qs = Object.entries(params as Record<string, unknown>)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join("&");
  return qs ? `?${qs}` : "";
}

// ----- Projects -----
export async function listProjects(
  params?: ProjectListParams,
): Promise<PaginatedResponse<Project>> {
  return fetchJson<PaginatedResponse<Project>>(`/api/v1/projects/${toQs(params)}`);
}

export async function getProject(id: string): Promise<ProjectDetail> {
  return fetchJson<ProjectDetail>(`/api/v1/projects/${id}`);
}

export async function createProject(data: {
  name: string;
  description?: string | null;
  status?: ProjectStatus;
  start_date?: string | null;
  end_date?: string | null;
  owner: string;
  tag_ids?: string[];
}): Promise<Project> {
  return fetchJson<Project>("/api/v1/projects/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateProject(
  id: string,
  data: Partial<{
    name: string;
    description: string | null;
    status: ProjectStatus;
    start_date: string | null;
    end_date: string | null;
    owner: string;
    tag_ids: string[];
  }>,
): Promise<Project> {
  return fetchJson<Project>(`/api/v1/projects/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteProject(id: string): Promise<void> {
  await fetchJson(`/api/v1/projects/${id}`, { method: "DELETE" });
}

export async function projectStats(id: string): Promise<ProjectStats> {
  return fetchJson<ProjectStats>(`/api/v1/projects/${id}/stats`);
}

// ----- Tasks -----
export async function listTasks(
  params?: TaskListParams,
): Promise<PaginatedResponse<Task>> {
  return fetchJson<PaginatedResponse<Task>>(`/api/v1/tasks/${toQs(params)}`);
}

export async function getTask(id: string): Promise<Task> {
  return fetchJson<Task>(`/api/v1/tasks/${id}`);
}

export async function createTask(data: {
  project_id: string;
  parent_task_id?: string | null;
  title: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  assignee?: string | null;
  due_date?: string | null;
  estimated_hours?: number | null;
  tag_ids?: string[];
}): Promise<Task> {
  return fetchJson<Task>("/api/v1/tasks/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTask(
  id: string,
  data: Partial<{
    project_id: string;
    parent_task_id: string | null;
    title: string;
    description: string | null;
    status: TaskStatus;
    priority: TaskPriority;
    assignee: string | null;
    due_date: string | null;
    estimated_hours: number | null;
    tag_ids: string[];
  }>,
): Promise<Task> {
  return fetchJson<Task>(`/api/v1/tasks/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteTask(id: string): Promise<void> {
  await fetchJson(`/api/v1/tasks/${id}`, { method: "DELETE" });
}

export async function bulkUpdateTasks(
  ids: string[],
  patch: Partial<{ status: TaskStatus; priority: TaskPriority; assignee: string }>,
): Promise<Task[]> {
  return fetchJson<Task[]>("/api/v1/tasks/bulk", {
    method: "POST",
    body: JSON.stringify({ ids, patch }),
  });
}

export async function listSubtasks(taskId: string): Promise<Task[]> {
  return fetchJson<Task[]>(`/api/v1/tasks/${taskId}/subtasks`);
}

export async function tasksDueToday(): Promise<Task[]> {
  return fetchJson<Task[]>("/api/v1/tasks/stats/due-today");
}

export async function tasksOverdue(): Promise<Task[]> {
  return fetchJson<Task[]>("/api/v1/tasks/stats/overdue");
}

export async function completedTasksCount(): Promise<{ count: number }> {
  return fetchJson<{ count: number }>("/api/v1/tasks/stats/completed-count");
}

// ----- Comments -----
export async function listTaskComments(taskId: string): Promise<Comment[]> {
  return fetchJson<Comment[]>(`/api/v1/tasks/${taskId}/comments`);
}

export async function createTaskComment(
  taskId: string,
  data: { author: string; body: string },
): Promise<Comment> {
  return fetchJson<Comment>(`/api/v1/tasks/${taskId}/comments`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateComment(
  commentId: string,
  data: { body: string },
): Promise<Comment> {
  return fetchJson<Comment>(`/api/v1/tasks/comments/${commentId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteComment(commentId: string): Promise<void> {
  await fetchJson(`/api/v1/tasks/comments/${commentId}`, { method: "DELETE" });
}

// ----- Milestones -----
export async function listMilestones(): Promise<Milestone[]> {
  return fetchJson<Milestone[]>("/api/v1/milestones/");
}

export async function getMilestone(id: string): Promise<Milestone> {
  return fetchJson<Milestone>(`/api/v1/milestones/${id}`);
}

export async function createMilestone(data: {
  project_id: string;
  name: string;
  description?: string | null;
  target_date: string;
  completed?: boolean;
}): Promise<Milestone> {
  return fetchJson<Milestone>("/api/v1/milestones/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateMilestone(
  id: string,
  data: Partial<{
    name: string;
    description: string | null;
    target_date: string;
    completed: boolean;
  }>,
): Promise<Milestone> {
  return fetchJson<Milestone>(`/api/v1/milestones/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteMilestone(id: string): Promise<void> {
  await fetchJson(`/api/v1/milestones/${id}`, { method: "DELETE" });
}

// ----- Tags -----
export async function listTags(): Promise<Tag[]> {
  return fetchJson<Tag[]>("/api/v1/tags/");
}

export async function createTag(data: { name: string; color?: string }): Promise<Tag> {
  return fetchJson<Tag>("/api/v1/tags/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTag(
  id: string,
  data: Partial<{ name: string; color: string }>,
): Promise<Tag> {
  return fetchJson<Tag>(`/api/v1/tags/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteTag(id: string): Promise<void> {
  await fetchJson(`/api/v1/tags/${id}`, { method: "DELETE" });
}

// ----- Demo seed / clear (self-contained utility — see SeedControls.tsx) -----
export interface SeedResult {
  seeded: boolean;
  access_token: string;
  demo_email: string;
  demo_password: string;
  workspace: string;
  projects: number;
  tasks: number;
  subtasks: number;
  milestones: number;
  comments: number;
}

export async function seedDemoData(): Promise<SeedResult> {
  return fetchJson<SeedResult>("/api/v1/seed", { method: "POST" });
}

export async function clearDemoData(): Promise<{ cleared: boolean }> {
  return fetchJson<{ cleared: boolean }>("/api/v1/seed", { method: "DELETE" });
}
