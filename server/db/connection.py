"""SQLite connection helpers and schema setup."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS research_tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    status TEXT NOT NULL,
    progress_stage TEXT,
    error_message TEXT,
    failed_stage TEXT,
    report_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research_reports (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    signal TEXT NOT NULL,
    summary TEXT NOT NULL,
    state_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES agent_sessions(id)
);

CREATE TABLE IF NOT EXISTS page_contexts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    page TEXT NOT NULL,
    context_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES agent_sessions(id)
);

-- 交易闭环（决策 → 模拟下单 → 结算复盘）

CREATE TABLE IF NOT EXISTS trading_accounts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    initial_cash REAL NOT NULL,
    cash REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
);

CREATE TABLE IF NOT EXISTS trade_decisions (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    rating TEXT NOT NULL,
    action TEXT,
    entry_price REAL,
    stop_loss REAL,
    price_target REAL,
    position_pct REAL,
    settlement_days INTEGER NOT NULL DEFAULT 20,
    status TEXT NOT NULL DEFAULT 'draft',
    judge_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(report_id) REFERENCES research_reports(id)
);

CREATE TABLE IF NOT EXISTS trade_orders (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    exec_date TEXT NOT NULL,
    fill_price REAL,
    fill_quantity INTEGER,
    fee_amount REAL,
    reject_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(decision_id) REFERENCES trade_decisions(id),
    FOREIGN KEY(account_id) REFERENCES trading_accounts(id)
);

CREATE TABLE IF NOT EXISTS trade_settlements (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    settle_date TEXT NOT NULL,
    ref_price REAL,
    settle_price REAL,
    decision_return REAL,
    benchmark_return REAL,
    excess_return REAL,
    outcome TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(decision_id) REFERENCES trade_decisions(id)
);

CREATE TABLE IF NOT EXISTS judge_calls (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    judge_name TEXT NOT NULL,
    verdict TEXT NOT NULL,
    latency_ms INTEGER,
    detail_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(decision_id) REFERENCES trade_decisions(id)
);

CREATE TABLE IF NOT EXISTS account_equity (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    date TEXT NOT NULL,
    cash REAL NOT NULL,
    market_value REAL NOT NULL,
    total_equity REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(account_id) REFERENCES trading_accounts(id),
    UNIQUE(account_id, date)
);

-- 止损/目标价监控告警（持仓 vs 决策阈值，refresh 时扫描）

CREATE TABLE IF NOT EXISTS trade_alerts (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    kind TEXT NOT NULL,
    price REAL NOT NULL,
    threshold REAL NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(account_id) REFERENCES trading_accounts(id)
);

-- 自动化：自选股 + 调度设置

CREATE TABLE IF NOT EXISTS watchlist (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    ticker TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS automation_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    enabled INTEGER NOT NULL DEFAULT 0,
    run_time TEXT NOT NULL DEFAULT '16:30',
    last_run_date TEXT
);

-- 市场数据底座：批量日线行情 + 股票池元信息 + 同步任务（Factor/Strategy Lab 数据源）

CREATE TABLE IF NOT EXISTS bars (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    amount REAL,
    PRIMARY KEY (symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_bars_date ON bars (date);

CREATE TABLE IF NOT EXISTS stock_meta (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    industry TEXT,
    universe TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_sync_runs (
    id TEXT PRIMARY KEY,
    universe TEXT NOT NULL,
    status TEXT NOT NULL,
    total_symbols INTEGER NOT NULL DEFAULT 0,
    done_symbols INTEGER NOT NULL DEFAULT 0,
    failed_symbols TEXT NOT NULL DEFAULT '',
    error_message TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);

-- Factor Lab：因子评价结果（因子值即算即用不落库，只存评价结论）

CREATE TABLE IF NOT EXISTS factor_evals (
    id TEXT PRIMARY KEY,
    factor_key TEXT NOT NULL,
    params TEXT NOT NULL,
    universe TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    n_periods INTEGER NOT NULL DEFAULT 0,
    ic_mean REAL,
    ic_std REAL,
    icir REAL,
    win_rate REAL,
    long_short_annual REAL,
    quantile_annuals TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Strategy Lab：策略回测记录（策略规则随 run 保存，明细以 JSON 存储）

CREATE TABLE IF NOT EXISTS strategy_runs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    rules TEXT NOT NULL,
    universe TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    n_periods INTEGER NOT NULL DEFAULT 0,
    annual_return REAL,
    annual_vol REAL,
    sharpe REAL,
    max_drawdown REAL,
    win_rate REAL,
    avg_turnover REAL,
    benchmark_annual_return REAL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

# 已有库的结构迁移：新增列补齐（CREATE TABLE IF NOT EXISTS 不会改动旧表）
_MIGRATIONS = [
    (
        "research_tasks",
        [
            ("prompt_tokens", "INTEGER NOT NULL DEFAULT 0"),
            ("completion_tokens", "INTEGER NOT NULL DEFAULT 0"),
            ("total_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ],
    ),
]


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in _MIGRATIONS:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if not existing:
            continue
        for name, ddl in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)
