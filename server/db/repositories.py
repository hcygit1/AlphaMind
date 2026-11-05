"""Repository helpers for the workbench SQLite database."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from server.core.config import DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID
from server.db.connection import connect


def _uuid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _dict(row: Any) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def upsert_default_identity(db_path: Path | str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, display_name) VALUES (?, ?)",
            (DEFAULT_USER_ID, "Default User"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO workspaces (id, user_id, name) VALUES (?, ?, ?)",
            (DEFAULT_WORKSPACE_ID, DEFAULT_USER_ID, "Default Workspace"),
        )


def create_research_task(db_path: Path | str, ticker: str, trade_date: str) -> dict[str, Any]:
    task_id = _uuid("task")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO research_tasks
            (id, user_id, workspace_id, ticker, trade_date, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID, ticker, trade_date, "pending"),
        )
        row = conn.execute("SELECT * FROM research_tasks WHERE id = ?", (task_id,)).fetchone()
    return _dict(row)


def create_research_task_if_none_active(
    db_path: Path | str,
    ticker: str,
    trade_date: str,
) -> dict[str, Any]:
    task_id = _uuid("task")
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        active = conn.execute(
            """
            SELECT id FROM research_tasks
            WHERE user_id = ? AND workspace_id = ? AND status IN ('pending', 'running')
            LIMIT 1
            """,
            (DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID),
        ).fetchone()
        if active:
            raise RuntimeError("同一默认用户同时只能运行一个深度投研任务")
        conn.execute(
            """
            INSERT INTO research_tasks
            (id, user_id, workspace_id, ticker, trade_date, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID, ticker, trade_date, "pending"),
        )
        row = conn.execute("SELECT * FROM research_tasks WHERE id = ?", (task_id,)).fetchone()
    return _dict(row)


def update_research_task(db_path: Path | str, task_id: str, **fields: Any) -> dict[str, Any]:
    allowed = {
        "status",
        "progress_stage",
        "error_message",
        "failed_stage",
        "report_id",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    }
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return get_research_task(db_path, task_id)

    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [task_id]
    with connect(db_path) as conn:
        conn.execute(
            f"UPDATE research_tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
        row = conn.execute("SELECT * FROM research_tasks WHERE id = ?", (task_id,)).fetchone()
    return _dict(row)


def get_research_task(db_path: Path | str, task_id: str) -> dict[str, Any]:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM research_tasks WHERE id = ?", (task_id,)).fetchone()
    return _dict(row)


def upsert_report(
    db_path: Path | str,
    ticker: str,
    trade_date: str,
    signal: str,
    summary: str,
    state_path: str,
) -> dict[str, Any]:
    report_id = _uuid("report")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO research_reports
            (id, user_id, workspace_id, ticker, trade_date, signal, summary, state_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                DEFAULT_USER_ID,
                DEFAULT_WORKSPACE_ID,
                ticker,
                trade_date,
                signal,
                summary,
                state_path,
            ),
        )
        row = conn.execute("SELECT * FROM research_reports WHERE id = ?", (report_id,)).fetchone()
    return _dict(row)


def list_reports(db_path: Path | str) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM research_reports ORDER BY created_at DESC, trade_date DESC, id DESC"
        ).fetchall()
    return [_dict(row) for row in rows]


def list_active_research_tasks(db_path: Path | str) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM research_tasks
            WHERE user_id = ? AND workspace_id = ? AND status IN ('pending', 'running')
            ORDER BY created_at ASC, id ASC
            """,
            (DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID),
        ).fetchall()
    return [_dict(row) for row in rows]


def cancel_active_research_tasks(db_path: Path | str, message: str) -> int:
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE research_tasks
            SET status = 'cancelled',
                error_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
              AND workspace_id = ?
              AND status IN ('pending', 'running')
            """,
            (message, DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID),
        )
    return cursor.rowcount


def get_report(db_path: Path | str, report_id: str) -> dict[str, Any]:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM research_reports WHERE id = ?", (report_id,)).fetchone()
    return _dict(row)


def create_agent_session(db_path: Path | str, title: str = "默认会话") -> dict[str, Any]:
    session_id = _uuid("session")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO agent_sessions (id, user_id, workspace_id, title)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID, title),
        )
        row = conn.execute("SELECT * FROM agent_sessions WHERE id = ?", (session_id,)).fetchone()
    return _dict(row)


def get_agent_session(db_path: Path | str, session_id: str) -> dict[str, Any]:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM agent_sessions WHERE id = ?", (session_id,)).fetchone()
    return _dict(row)


def add_agent_message(
    db_path: Path | str,
    session_id: str,
    role: str,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    message_id = _uuid("msg")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO agent_messages (id, session_id, role, content, tool_calls_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (message_id, session_id, role, content, json.dumps(tool_calls or [], ensure_ascii=False)),
        )
        row = conn.execute("SELECT * FROM agent_messages WHERE id = ?", (message_id,)).fetchone()
    message = _dict(row)
    message["tool_calls_json"] = json.loads(message["tool_calls_json"])
    return message


def list_agent_messages(db_path: Path | str, session_id: str) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM agent_messages WHERE session_id = ? ORDER BY created_at ASC, rowid ASC",
            (session_id,),
        ).fetchall()
    messages = [_dict(row) for row in rows]
    for message in messages:
        message["tool_calls_json"] = json.loads(message["tool_calls_json"])
    return messages


def save_page_context(
    db_path: Path | str,
    session_id: str,
    page: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    context_id = _uuid("ctx")
    with connect(db_path) as conn:
        conn.execute("DELETE FROM page_contexts WHERE session_id = ?", (session_id,))
        conn.execute(
            """
            INSERT INTO page_contexts
            (id, session_id, user_id, workspace_id, page, context_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                context_id,
                session_id,
                DEFAULT_USER_ID,
                DEFAULT_WORKSPACE_ID,
                page,
                json.dumps(context, ensure_ascii=False),
            ),
        )
        row = conn.execute(
            "SELECT * FROM page_contexts WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    saved = _dict(row)
    saved["context_json"] = json.loads(saved["context_json"])
    return saved


def get_page_context(db_path: Path | str, session_id: str) -> dict[str, Any]:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM page_contexts WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    context = _dict(row)
    if context:
        context["context_json"] = json.loads(context["context_json"])
    return context


# ---- 自选股与自动投研调度 ----


def list_watchlist(db_path: Path | str, enabled_only: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT * FROM watchlist"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY created_at ASC, rowid ASC"
    with connect(db_path) as conn:
        rows = conn.execute(sql).fetchall()
    return [_dict(row) for row in rows]


def add_watchlist_ticker(db_path: Path | str, ticker: str) -> dict[str, Any]:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO watchlist (id, user_id, workspace_id, ticker)
            VALUES (?, ?, ?, ?)
            """,
            (_uuid("wl"), DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID, ticker),
        )
        row = conn.execute(
            "SELECT * FROM watchlist WHERE ticker = ?", (ticker,)
        ).fetchone()
    return _dict(row)


def remove_watchlist_ticker(db_path: Path | str, ticker: str) -> bool:
    with connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
    return cursor.rowcount > 0


def get_automation_settings(db_path: Path | str) -> dict[str, Any]:
    """读自动投研设置（单行表，不存在则给默认值）。"""
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM automation_settings WHERE id = 1").fetchone()
    if row:
        return _dict(row)
    return {"id": 1, "enabled": 0, "run_time": "16:30", "last_run_date": None}


def update_automation_settings(
    db_path: Path | str,
    enabled: int | None = None,
    run_time: str | None = None,
    last_run_date: str | None = None,
) -> dict[str, Any]:
    get_automation_settings(db_path)  # 确保默认行存在（首次 UPSERT）
    updates: dict[str, Any] = {}
    if enabled is not None:
        updates["enabled"] = int(enabled)
    if run_time is not None:
        updates["run_time"] = run_time
    if last_run_date is not None:
        updates["last_run_date"] = last_run_date
    if not updates:
        return get_automation_settings(db_path)

    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values())
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO automation_settings (id, enabled, run_time) VALUES (1, 0, '16:30')
            ON CONFLICT(id) DO NOTHING
            """
        )
        conn.execute(
            f"UPDATE automation_settings SET {assignments} WHERE id = 1",
            values,
        )
        row = conn.execute("SELECT * FROM automation_settings WHERE id = 1").fetchone()
    return _dict(row)


# ---- 市场数据底座：bars / stock_meta / 同步任务 ----


def upsert_stock_meta(db_path: Path | str, universe: str, rows: list[dict[str, Any]]) -> int:
    """整池替换指定 universe 的成分股元信息（成分调整后旧的剔除）。"""
    with connect(db_path) as conn:
        conn.execute("DELETE FROM stock_meta WHERE universe = ?", (universe,))
        conn.executemany(
            """
            INSERT INTO stock_meta (symbol, name, industry, universe)
            VALUES (?, ?, ?, ?)
            """,
            [(r["symbol"], r["name"], r.get("industry"), universe) for r in rows],
        )
    return len(rows)


def list_stock_meta(db_path: Path | str, universe: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT symbol, name, industry, universe FROM stock_meta"
    params: tuple = ()
    if universe:
        sql += " WHERE universe = ?"
        params = (universe,)
    sql += " ORDER BY symbol ASC"
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_dict(row) for row in rows]


def upsert_bars(db_path: Path | str, symbol: str, bars: list[dict[str, Any]]) -> int:
    """批量写入日线（按主键 symbol+date 幂等覆盖）。"""
    if not bars:
        return 0
    with connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO bars (symbol, date, open, high, low, close, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    symbol,
                    b["date"],
                    b["open"],
                    b["high"],
                    b["low"],
                    b["close"],
                    b["volume"],
                    b.get("amount"),
                )
                for b in bars
            ],
        )
    return len(bars)


def get_bars(
    db_path: Path | str,
    symbol: str,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT date, open, high, low, close, volume, amount FROM bars WHERE symbol = ?"
    params: list[Any] = [symbol]
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date <= ?"
        params.append(end)
    sql += " ORDER BY date ASC"
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_dict(row) for row in rows]


def get_market_stats(db_path: Path | str) -> dict[str, Any]:
    """底座数据汇总：股票数 / K 线总数 / 最早最晚日期。"""
    with connect(db_path) as conn:
        symbols = conn.execute("SELECT COUNT(*) AS n FROM stock_meta").fetchone()["n"]
        bars = conn.execute("SELECT COUNT(*) AS n FROM bars").fetchone()["n"]
        row = conn.execute(
            "SELECT MIN(date) AS min_date, MAX(date) AS max_date FROM bars"
        ).fetchone()
    return {
        "symbols": symbols,
        "bars": bars,
        "min_date": row["min_date"] if row else None,
        "max_date": row["max_date"] if row else None,
    }


def create_sync_run(db_path: Path | str, universe: str, total_symbols: int) -> dict[str, Any]:
    run_id = _uuid("msync")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO market_sync_runs (id, universe, status, total_symbols)
            VALUES (?, ?, 'running', ?)
            """,
            (run_id, universe, total_symbols),
        )
        row = conn.execute("SELECT * FROM market_sync_runs WHERE id = ?", (run_id,)).fetchone()
    return _dict(row)


def update_sync_run(db_path: Path | str, run_id: str, **fields: Any) -> dict[str, Any]:
    if fields:
        assignments = ", ".join(f"{key} = ?" for key in fields)
        with connect(db_path) as conn:
            conn.execute(
                f"UPDATE market_sync_runs SET {assignments} WHERE id = ?",
                [*fields.values(), run_id],
            )
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM market_sync_runs WHERE id = ?", (run_id,)).fetchone()
    return _dict(row)


def get_latest_sync_run(db_path: Path | str, universe: str) -> dict[str, Any]:
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM market_sync_runs
            WHERE universe = ?
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """,
            (universe,),
        ).fetchone()
    return _dict(row)


def interrupt_stale_sync_runs(db_path: Path | str) -> int:
    """服务启动时把遗留的 running 同步标记为失败（线程已随进程终止）。"""
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE market_sync_runs
            SET status = 'failed',
                error_message = '服务重启，同步已中断',
                finished_at = CURRENT_TIMESTAMP
            WHERE status = 'running'
            """
        )
    return cursor.rowcount


# ---- Factor Lab：面板数据 + 因子评价结果 ----


def fetch_all_bars(
    db_path: Path | str,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    """全池收盘价/成交量（因子面板数据源）。"""
    sql = "SELECT symbol, date, close, volume FROM bars"
    params: list[Any] = []
    if start:
        sql += " WHERE date >= ?"
        params.append(start)
    if end:
        sql += f" {'AND' if params else 'WHERE'} date <= ?"
        params.append(end)
    sql += " ORDER BY date ASC, symbol ASC"
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_dict(row) for row in rows]


def save_factor_eval(
    db_path: Path | str,
    factor_key: str,
    params: dict[str, Any],
    universe: str,
    start_date: str | None,
    end_date: str | None,
    summary: dict[str, Any],
) -> dict[str, Any]:
    eval_id = _uuid("feval")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO factor_evals
            (id, factor_key, params, universe, start_date, end_date,
             n_periods, ic_mean, ic_std, icir, win_rate, long_short_annual, quantile_annuals)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eval_id,
                factor_key,
                json.dumps(params, ensure_ascii=False),
                universe,
                start_date,
                end_date,
                summary.get("n_periods") or 0,
                summary.get("ic_mean"),
                summary.get("ic_std"),
                summary.get("icir"),
                summary.get("win_rate"),
                summary.get("long_short_annual"),
                json.dumps(summary.get("quantile_annuals") or {}, ensure_ascii=False),
            ),
        )
        row = conn.execute("SELECT * FROM factor_evals WHERE id = ?", (eval_id,)).fetchone()
    return _dict(row)


def list_factor_evals(
    db_path: Path | str,
    factor_key: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM factor_evals"
    params: list[Any] = []
    if factor_key:
        sql += " WHERE factor_key = ?"
        params.append(factor_key)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_dict(row) for row in rows]


# ---- Strategy Lab：策略回测记录 ----


def save_strategy_run(
    db_path: Path | str,
    name: str,
    rules: dict[str, Any],
    universe: str,
    start_date: str | None,
    end_date: str | None,
    metrics: dict[str, Any],
    detail: dict[str, Any],
) -> dict[str, Any]:
    run_id = _uuid("srun")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO strategy_runs
            (id, name, rules, universe, start_date, end_date, n_periods,
             annual_return, annual_vol, sharpe, max_drawdown, win_rate,
             avg_turnover, benchmark_annual_return, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                name,
                json.dumps(rules, ensure_ascii=False),
                universe,
                start_date,
                end_date,
                metrics.get("n_periods") or 0,
                metrics.get("annual_return"),
                metrics.get("annual_vol"),
                metrics.get("sharpe"),
                metrics.get("max_drawdown"),
                metrics.get("win_rate"),
                metrics.get("avg_turnover"),
                metrics.get("benchmark_annual_return"),
                json.dumps(detail, ensure_ascii=False),
            ),
        )
        row = conn.execute("SELECT * FROM strategy_runs WHERE id = ?", (run_id,)).fetchone()
    return _dict(row)


def list_strategy_runs(
    db_path: Path | str,
    name: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """回测记录列表（不含 detail 大字段）。"""
    sql = (
        "SELECT id, name, rules, universe, start_date, end_date, n_periods,"
        " annual_return, annual_vol, sharpe, max_drawdown, win_rate,"
        " avg_turnover, benchmark_annual_return, created_at FROM strategy_runs"
    )
    params: list[Any] = []
    if name:
        sql += " WHERE name = ?"
        params.append(name)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_dict(row) for row in rows]


def get_strategy_run(db_path: Path | str, run_id: str) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM strategy_runs WHERE id = ?", (run_id,)).fetchone()
    return _dict(row) if row else None
