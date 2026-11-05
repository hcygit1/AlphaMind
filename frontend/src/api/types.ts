export type ResearchTask = {
  id: string;
  ticker: string;
  trade_date: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  progress_stage?: string | null;
  report_id?: string | null;
  error_message?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
};

export type WatchlistItem = {
  id: string;
  ticker: string;
  /** 后端存 SQLite INTEGER 0/1，client 层归一化为 boolean */
  enabled: boolean;
  created_at: string;
};

export type AutomationSettings = {
  id: number;
  /** 后端存 SQLite INTEGER 0/1，client 层归一化为 boolean */
  enabled: boolean;
  run_time: string;
  last_run_date?: string | null;
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

// ---- Paper Trading ----

export type TradingAccount = {
  id: string;
  name: string;
  initial_cash: number;
  cash: number;
  status: string;
};

export type TradingPosition = {
  ticker: string;
  quantity: number;
  available: number;
  cost_total: number;
  avg_cost: number;
};

export type TradingOrder = {
  id: string;
  decision_id: string;
  ticker: string;
  side: string;
  quantity: number;
  exec_date: string;
  status: string;
  fill_price?: number | null;
  fill_quantity?: number | null;
  fee_amount?: number | null;
  reject_reason?: string | null;
  created_at: string;
};

export type TradeDecision = {
  id: string;
  report_id: string;
  ticker: string;
  trade_date: string;
  rating?: string | null;
  action?: string | null;
  entry_price?: number | null;
  stop_loss?: number | null;
  price_target?: number | null;
  position_pct?: number | null;
  settlement_days: number;
  status: string;
  created_at: string;
};

export type TradeSettlement = {
  id: string;
  decision_id: string;
  settle_date: string;
  ref_price: number;
  settle_price: number;
  decision_return: number;
  benchmark_return?: number | null;
  excess_return?: number | null;
  outcome: string;
};

export type EquitySnapshot = {
  id: string;
  account_id: string;
  date: string;
  cash: number;
  market_value: number;
  total_equity: number;
};

export type TradingAccountResponse = {
  account: TradingAccount;
  positions: TradingPosition[];
  orders: TradingOrder[];
};

export type TradeAlert = {
  id: string;
  account_id: string;
  ticker: string;
  kind: "stop_loss_hit" | "price_target_hit";
  price: number;
  threshold: number;
  message: string;
  status: "open" | "acked";
  created_at: string;
};

export type RefreshResponse = {
  orders: { filled: number; rejected: number; postponed: number; cancelled: number };
  settlements: TradeSettlement[];
  equity: EquitySnapshot;
  alerts: TradeAlert[];
};

export type ExecuteDecisionResponse = {
  status: "executing" | "executed" | "skipped" | "blocked" | "rejected" | "failed";
  order?: TradingOrder;
  orders?: TradingOrder[];
  reason?: string;
};

// ---- Factor Lab ----

export type FactorMeta = {
  key: string;
  default_params: Record<string, number>;
  description: string;
};

export type FactorEvalSummary = {
  n_periods: number;
  ic_mean?: number | null;
  ic_std?: number | null;
  icir?: number | null;
  win_rate?: number | null;
  long_short_annual?: number | null;
  quantile_annuals?: Record<string, number | null> | null;
};

export type FactorEvalResponse = {
  eval_id: string;
  factor: string;
  params: Record<string, number>;
  start_date: string;
  end_date: string;
  summary: FactorEvalSummary;
  ic_series: { date: string; ic: number | null }[];
  quantile?: { dates: string[]; navs: Record<string, number[]> } | null;
  long_short_nav?: number[] | null;
};

export type FactorEvalRecord = {
  id: string;
  factor_key: string;
  params: string;
  start_date: string;
  end_date: string;
  n_periods: number;
  ic_mean?: number | null;
  icir?: number | null;
  win_rate?: number | null;
  long_short_annual?: number | null;
  created_at: string;
};

// ---- Strategy Lab ----

export type StrategyTemplate = {
  key: string;
  name: string;
  description: string;
  rules: Record<string, unknown>;
};

export type BacktestMetrics = {
  n_periods: number;
  annual_return?: number | null;
  annual_vol?: number | null;
  sharpe?: number | null;
  max_drawdown?: number | null;
  win_rate?: number | null;
  avg_turnover?: number | null;
  benchmark_annual_return?: number | null;
  n_limit_up_blocked?: number | null;
};

export type BacktestPeriod = {
  date: string;
  holdings: string[];
  ret: number;
  turnover: number;
  cost: number;
};

export type BacktestResponse = {
  run_id: string;
  name: string;
  rules: Record<string, unknown>;
  start_date: string;
  end_date: string;
  created_at?: string;
  metrics: BacktestMetrics;
  nav_curve: { dates: string[]; nav: number[]; benchmark_nav: number[] };
  periods: BacktestPeriod[];
};

export type StrategyRunRecord = {
  id: string;
  name: string;
  rules: Record<string, unknown>;
  start_date: string;
  end_date: string;
  n_periods: number;
  annual_return?: number | null;
  sharpe?: number | null;
  max_drawdown?: number | null;
  win_rate?: number | null;
  avg_turnover?: number | null;
  benchmark_annual_return?: number | null;
  created_at: string;
  detail?: {
    nav_curve: BacktestResponse["nav_curve"];
    periods: BacktestPeriod[];
    n_limit_up_blocked?: number | null;
  } | null;
};
