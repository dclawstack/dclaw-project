const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export type CopilotProvider = "openrouter" | "ollama" | "heuristic" | "fallback-template";

export interface CopilotMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface CopilotChatResponse {
  text: string;
  provider: CopilotProvider | string;
  model: string;
  tokens_in: number | null;
  tokens_out: number | null;
}

export interface ProjectHealthResponse {
  project_id: string;
  score: number;
  status: "green" | "yellow" | "red";
  narrative: string;
  signals: { label: string; weight: number; penalty: number }[];
  top_risks: string[];
}

export interface GenerateWBSRequest {
  goal: string;
  deadline_days: number;
  team_size: number;
  project_id?: string;
  project_name?: string;
  owner?: string;
}

export interface GenerateWBSResponse {
  project_id: string;
  tasks: {
    title: string;
    description: string;
    priority: string;
    estimated_hours: number;
    depends_on: number[];
  }[];
  milestones: {
    name: string;
    target_offset_days: number;
    target_date: string;
  }[];
  provider: string;
  model: string;
  created_task_ids: string[];
  created_milestone_ids: string[];
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    throw new Error(`API error ${resp.status}: ${await resp.text()}`);
  }
  return resp.json();
}

export async function copilotChat(
  messages: CopilotMessage[],
  projectId?: string,
): Promise<CopilotChatResponse> {
  return postJson<CopilotChatResponse>("/api/v1/ai/copilot/chat", {
    messages,
    project_id: projectId,
  });
}

export async function projectHealth(projectId: string): Promise<ProjectHealthResponse> {
  const resp = await fetch(`${API_BASE}/api/v1/ai/projects/${projectId}/health`);
  if (!resp.ok) throw new Error(`API error ${resp.status}`);
  return resp.json();
}

export async function generateWBS(req: GenerateWBSRequest): Promise<GenerateWBSResponse> {
  return postJson<GenerateWBSResponse>("/api/v1/ai/generate-wbs", req);
}
