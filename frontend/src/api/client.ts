import type { AgentResponse, AgentSession, ReportDetailResponse, ReportSummary, ResearchTask } from "./types";

export const AGENT_SESSION_STORAGE_KEY = "alphamind_session_id";
export const AGENT_SESSION_READY_EVENT = "alphamind-agent-session-ready";
export const AGENT_CONTEXT_SYNC_EVENT = "alphamind-agent-context-sync";

export type AgentContextSyncDetail = {
  sessionId: string;
  tasks: Promise<unknown>[];
};

const API_BASE =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ??
  "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    }
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(formatApiError(text, response.statusText));
  }

  return response.json() as Promise<T>;
}

function formatApiError(text: string, fallback: string) {
  if (!text) {
    return fallback;
  }

  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    return typeof parsed.detail === "string" ? parsed.detail : text;
  } catch {
    return text;
  }
}

export function createResearchTask(ticker: string, tradeDate: string) {
  return request<ResearchTask>("/api/research/tasks", {
    method: "POST",
    body: JSON.stringify({ ticker, trade_date: tradeDate })
  });
}

export function listReports() {
  return request<ReportSummary[]>("/api/reports");
}

export function getReport(reportId: string) {
  return request<ReportDetailResponse>(`/api/reports/${reportId}`);
}

export function researchEventsUrl(taskId: string) {
  return `${API_BASE}/api/research/tasks/${taskId}/events`;
}

export function createAgentSession(title = "默认会话") {
  return request<AgentSession>("/api/agent/sessions", {
    method: "POST",
    body: JSON.stringify({ title })
  });
}

export function sendAgentMessage(sessionId: string, content: string) {
  return request<AgentResponse>(`/api/agent/sessions/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content })
  });
}

export function savePageContext(sessionId: string, page: string, context: Record<string, unknown>) {
  return request<Record<string, unknown>>("/api/runtime/page-context", {
    method: "PUT",
    body: JSON.stringify({ session_id: sessionId, page, context })
  });
}

export function currentAgentSessionId() {
  return window.localStorage.getItem(AGENT_SESSION_STORAGE_KEY);
}

export function persistAgentSessionId(sessionId: string) {
  window.localStorage.setItem(AGENT_SESSION_STORAGE_KEY, sessionId);
  window.dispatchEvent(new Event(AGENT_SESSION_READY_EVENT));
}

export async function requestCurrentPageContextSync(sessionId: string) {
  const detail: AgentContextSyncDetail = { sessionId, tasks: [] };
  window.dispatchEvent(new CustomEvent<AgentContextSyncDetail>(AGENT_CONTEXT_SYNC_EVENT, { detail }));
  await Promise.allSettled(detail.tasks);
}
