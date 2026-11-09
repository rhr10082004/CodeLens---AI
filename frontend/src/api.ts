import type { Analysis, AnalysisSummary, GeneratedTestCase, GitHubFile, GitHubRepository, Language, User } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "codelens_access_token";

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function saveToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed (${response.status}).`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

interface SessionResponse {
  access_token: string;
  user: User;
}

export async function authenticate(
  mode: "login" | "register",
  values: { name?: string; email: string; password: string },
): Promise<User> {
  const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/register";
  const result = await request<SessionResponse>(endpoint, {
    method: "POST",
    body: JSON.stringify(values),
  });
  saveToken(result.access_token);
  return result.user;
}

export function whoAmI(): Promise<User> {
  return request<User>("/api/auth/me");
}

export function revokeSession(token: string): Promise<void> {
  return request<void>("/api/auth/logout", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function runAnalysis(
  language: Language,
  source_code: string,
  include_ai: boolean,
  retain_source: boolean,
): Promise<Analysis> {
  return request<Analysis>("/api/analyses", {
    method: "POST",
    body: JSON.stringify({ language, source_code, include_ai, retain_source }),
  });
}

export function generateTestCases(language: Language, source_code: string): Promise<GeneratedTestCase[]> {
  return request<GeneratedTestCase[]>("/api/test-cases", {
    method: "POST",
    body: JSON.stringify({ language, source_code }),
  });
}

export function listAnalyses(): Promise<AnalysisSummary[]> {
  return request<AnalysisSummary[]>("/api/analyses");
}

export function removeAnalysis(id: number): Promise<void> {
  return request<void>(`/api/analyses/${id}`, { method: "DELETE" });
}

export function browseGitHubRepository(
  url: string,
): Promise<{ repository: GitHubRepository; files: GitHubFile[] }> {
  return request("/api/github/repository", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function fetchGitHubFile(url: string, path: string): Promise<{ path: string; size: number; source_code: string }> {
  const query = new URLSearchParams({ path });
  return request(`/api/github/file?${query}`, {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}
