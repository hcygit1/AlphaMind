import type {
  AgentResponse,
  AgentSession,
  AutomationSettings,
  BacktestResponse,
  EquitySnapshot,
  ExecuteDecisionResponse,
  FactorEvalRecord,
  FactorEvalResponse,
  FactorMeta,
  RefreshResponse,
  ReportDetailResponse,
  ReportSummary,
  ResearchTask,
  StrategyRunRecord,
  StrategyTemplate,
  TradeAlert,
  TradeDecision,
  TradeSettlement,
  TradingAccountResponse,
  TradingOrder,
  WatchlistItem
} from "./types";

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

// GET 并发去重：同一时刻的重复请求共享一次网络往返；不做结果缓存，避免交易数据陈旧
const inflightGets = new Map<string, Promise<unknown>>();

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isGet = !init?.method || init.method === "GET";
  if (!isGet) {
    return fetchOnce<T>(path, init);
  }
  const existing = inflightGets.get(path) as Promise<T> | undefined;
  if (existing) {
    return existing;
  }
  const pending = fetchOnce<T>(path, init).finally(() => inflightGets.delete(path));
  inflightGets.set(path, pending);
  return pending;
}

const REQUEST_TIMEOUT_MS = 30_000;

async function fetchOnce<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers
      },
      signal: init?.signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS)
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new Error(`请求超时（${REQUEST_TIMEOUT_MS / 1000} 秒），请稍后重试`);
    }
    throw error;
  }

  if (!response.ok) {
    const text = await response.text();
    throw new Error(formatApiError(text, response.statusText));
  }

  // 204 / 空 body（部分 PUT、DELETE 接口）直接返回，避免 JSON 解析空串报错
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
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

export function cancelResearchTask(taskId: string) {
  return request<ResearchTask>(`/api/research/tasks/${taskId}/cancel`, {
    method: "POST"
  });
}

export function listReports() {
  return request<ReportSummary[]>("/api/reports");
}

export function getReport(reportId: string) {
  return request<ReportDetailResponse>(`/api/reports/${reportId}`);
}

export function getActiveResearchTask() {
  return request<ResearchTask | null>("/api/research/tasks/active");
}

export function getResearchTask(taskId: string) {
  return request<ResearchTask>(`/api/research/tasks/${taskId}`);
}

// ---- Automation ----

/** 后端 SQLite BOOLEAN 以 0/1 返回，统一归一化为 boolean */
function normalizeEnabled<T extends { enabled: unknown }>(row: T): Omit<T, "enabled"> & { enabled: boolean } {
  return { ...row, enabled: row.enabled === 1 || row.enabled === true };
}

export function listWatchlist() {
  return request<WatchlistItem[]>("/api/automation/watchlist").then((items) =>
    items.map(normalizeEnabled)
  );
}

export function addWatchlistTicker(ticker: string) {
  return request<WatchlistItem>(`/api/automation/watchlist/${encodeURIComponent(ticker)}`, {
    method: "POST"
  }).then(normalizeEnabled);
}

export function removeWatchlistTicker(ticker: string) {
  return request<{ removed: string }>(`/api/automation/watchlist/${encodeURIComponent(ticker)}`, {
    method: "DELETE"
  });
}

export function getAutomationSettings() {
  return request<AutomationSettings>("/api/automation/settings").then(normalizeEnabled);
}

export function updateAutomationSettings(payload: { enabled?: boolean; run_time?: string }) {
  return request<AutomationSettings>("/api/automation/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }).then(normalizeEnabled);
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

// ---- Paper Trading ----

export function getTradingAccount() {
  return request<TradingAccountResponse>("/api/trading/account");
}

export function listTradeDecisions() {
  return request<TradeDecision[]>("/api/trading/decisions");
}

export function executeTradeDecision(decisionId: string) {
  return request<ExecuteDecisionResponse>(`/api/trading/decisions/${decisionId}/execute`, {
    method: "POST"
  });
}

export function listTradingOrders() {
  return request<TradingOrder[]>("/api/trading/orders");
}

export function refreshTrading() {
  return request<RefreshResponse>("/api/trading/refresh", { method: "POST" });
}

export function listTradeSettlements() {
  return request<TradeSettlement[]>("/api/trading/settlements");
}

export function listEquitySnapshots() {
  return request<EquitySnapshot[]>("/api/trading/equity");
}

export function listTradeAlerts() {
  return request<TradeAlert[]>("/api/trading/alerts");
}

export function ackTradeAlert(alertId: string) {
  return request<TradeAlert>(`/api/trading/alerts/${alertId}/ack`, { method: "POST" });
}

export function persistAgentSessionId(sessionId: string) {
  window.localStorage.setItem(AGENT_SESSION_STORAGE_KEY, sessionId);
  window.dispatchEvent(new Event(AGENT_SESSION_READY_EVENT));
}

// ---- Factor Lab ----

export function listFactors() {
  return request<FactorMeta[]>("/api/factor/list");
}

export function evaluateFactor(payload: {
  factor: string;
  params?: Record<string, number> | null;
  start?: string | null;
  end?: string | null;
}) {
  return request<FactorEvalResponse>("/api/factor/eval", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function listFactorEvals(factor?: string) {
  const query = factor ? `?factor=${encodeURIComponent(factor)}` : "";
  return request<FactorEvalRecord[]>(`/api/factor/evals${query}`);
}

// ---- Strategy Lab ----

export function listStrategyTemplates() {
  return request<StrategyTemplate[]>("/api/strategy/templates");
}

export function runStrategyBacktest(payload: {
  name: string;
  rules: Record<string, unknown>;
  start?: string | null;
  end?: string | null;
}) {
  return request<BacktestResponse>("/api/strategy/backtest", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function listStrategyRuns(name?: string) {
  const query = name ? `?name=${encodeURIComponent(name)}` : "";
  return request<StrategyRunRecord[]>(`/api/strategy/runs${query}`);
}

export function getStrategyRun(runId: string) {
  return request<StrategyRunRecord>(`/api/strategy/runs/${encodeURIComponent(runId)}`);
}

export async function requestCurrentPageContextSync(sessionId: string) {
  const detail: AgentContextSyncDetail = { sessionId, tasks: [] };
  window.dispatchEvent(new CustomEvent<AgentContextSyncDetail>(AGENT_CONTEXT_SYNC_EVENT, { detail }));
  await Promise.allSettled(detail.tasks);
}
