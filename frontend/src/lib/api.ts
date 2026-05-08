const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API error ${response.status}: ${error}`);
  }
  return response.json();
}

export async function getHealth() {
  return fetchJson<{ status: string }>("/health/");
}

export type ProjectStatus = "planning" | "active" | "on_hold" | "completed" | "cancelled";
export type TaskStatus = "todo" | "in_progress" | "review" | "done";
export type TaskPriority = "low" | "medium" | "high" | "urgent";

export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  start_date: string | null;
  end_date: string | null;
  owner: string;
}

export interface ProjectDetail extends Project {
  tasks: Task[];
  milestones: Milestone[];
}

export interface Task {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  assignee: string | null;
  due_date: string | null;
}

export interface Milestone {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  target_date: string;
  completed: boolean;
}

export async function listProjects(): Promise<Project[]> {
  return fetchJson<Project[]>("/api/v1/projects/");
}

export async function getProject(id: string): Promise<ProjectDetail> {
  return fetchJson<ProjectDetail>(`/api/v1/projects/${id}`);
}

export async function createProject(data: Omit<Project, "id">): Promise<Project> {
  return fetchJson<Project>("/api/v1/projects/", { method: "POST", body: JSON.stringify(data) });
}

export async function updateProject(id: string, data: Partial<Omit<Project, "id">>): Promise<Project> {
  return fetchJson<Project>(`/api/v1/projects/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteProject(id: string): Promise<void> {
  await fetch(`/api/v1/projects/${id}`, { method: "DELETE" });
}

export async function listTasks(): Promise<Task[]> {
  return fetchJson<Task[]>("/api/v1/tasks/");
}

export async function getTask(id: string): Promise<Task> {
  return fetchJson<Task>(`/api/v1/tasks/${id}`);
}

export async function createTask(data: Omit<Task, "id">): Promise<Task> {
  return fetchJson<Task>("/api/v1/tasks/", { method: "POST", body: JSON.stringify(data) });
}

export async function updateTask(id: string, data: Partial<Omit<Task, "id">>): Promise<Task> {
  return fetchJson<Task>(`/api/v1/tasks/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteTask(id: string): Promise<void> {
  await fetch(`/api/v1/tasks/${id}`, { method: "DELETE" });
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

export async function listMilestones(): Promise<Milestone[]> {
  return fetchJson<Milestone[]>("/api/v1/milestones/");
}

export async function getMilestone(id: string): Promise<Milestone> {
  return fetchJson<Milestone>(`/api/v1/milestones/${id}`);
}

export async function createMilestone(data: Omit<Milestone, "id">): Promise<Milestone> {
  return fetchJson<Milestone>("/api/v1/milestones/", { method: "POST", body: JSON.stringify(data) });
}

export async function updateMilestone(id: string, data: Partial<Omit<Milestone, "id">>): Promise<Milestone> {
  return fetchJson<Milestone>(`/api/v1/milestones/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteMilestone(id: string): Promise<void> {
  await fetch(`/api/v1/milestones/${id}`, { method: "DELETE" });
}
