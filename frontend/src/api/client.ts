import type { ReportDetailResponse, ReportSummary, ResearchTask } from "./types";

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
