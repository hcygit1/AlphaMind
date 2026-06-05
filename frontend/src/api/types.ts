export type ResearchTask = {
  id: string;
  ticker: string;
  trade_date: string;
  status: "pending" | "running" | "completed" | "failed";
  progress_stage?: string | null;
  report_id?: string | null;
  error_message?: string | null;
};

export type ResearchProgressEvent = {
  event: "research_progress";
  task_id: string;
  status: ResearchTask["status"];
  stage?: string | null;
  message: string;
  payload?: {
    report_id?: string;
    [key: string]: unknown;
  };
};

export type ReportSummary = {
  id: string;
  ticker: string;
  trade_date: string;
  signal: string;
  summary: string;
  state_path: string;
  created_at: string;
};

export type ReportSection = {
  id: string;
  title: string;
  summary: string;
  raw: string;
};

export type ReportDetailResponse = {
  report: ReportSummary;
  sections: ReportSection[];
  state?: Record<string, unknown>;
};

export type AgentSession = {
  id: string;
  title: string;
};

export type AgentToolCard = {
  type: string;
  status?: string;
  payload: Record<string, unknown>;
};

export type AgentResponse = {
  message_id: string;
  role: "assistant";
  content: string;
  tool_cards: AgentToolCard[];
};
