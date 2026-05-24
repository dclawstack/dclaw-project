import { getAuthToken, setAuthToken } from "./api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
}

export interface AuthWorkspace {
  id: string;
  name: string;
  slug: string;
}

export interface AuthResult {
  access_token: string;
  user: AuthUser;
  workspace: AuthWorkspace;
}

async function authFetch<T>(path: string, body: unknown, method = "POST"): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const resp = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`auth error ${resp.status}: ${text}`);
  }
  return resp.json();
}

export async function register(input: {
  email: string;
  password: string;
  full_name?: string;
  workspace_name?: string;
}): Promise<AuthResult> {
  const result = await authFetch<AuthResult>("/api/v1/auth/register", input);
  setAuthToken(result.access_token);
  return result;
}

export async function login(email: string, password: string): Promise<AuthResult> {
  const result = await authFetch<AuthResult>("/api/v1/auth/login", { email, password });
  setAuthToken(result.access_token);
  return result;
}

export async function fetchMe(): Promise<{
  user: AuthUser;
  active_workspace: AuthWorkspace;
  workspaces: { workspace: AuthWorkspace; role: string }[];
}> {
  return authFetch("/api/v1/auth/me", null, "GET");
}

export function logout() {
  setAuthToken(null);
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
}
