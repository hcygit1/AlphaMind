"""交易闭环的 SQLite 仓库函数（账户 / 决策 / 订单 / 结算 / 净值）。"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from server.core.config import DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID
from server.db.connection import session
from server.trading.extraction import DecisionRecord
from server.trading.settings import INITIAL_CASH


def _uuid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _dict(row: Any) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def get_or_create_default_account(db_path: Path | str) -> dict[str, Any]:
    """返回默认用户的模拟账户，不存在则自动创建（初始资金见 settings）。"""
    with session(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM trading_accounts
            WHERE user_id = ? AND workspace_id = ? AND status = 'active'
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            (DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID),
        ).fetchone()
        if row:
            return _dict(row)

        account_id = _uuid("acct")
        conn.execute(
            """
            INSERT INTO trading_accounts
            (id, user_id, workspace_id, name, initial_cash, cash)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                DEFAULT_USER_ID,
                DEFAULT_WORKSPACE_ID,
                "模拟账户",
                INITIAL_CASH,
                INITIAL_CASH,
            ),
        )
        row = conn.execute(
            "SELECT * FROM trading_accounts WHERE id = ?", (account_id,)
        ).fetchone()
    return _dict(row)


def create_decision(
    db_path: Path | str,
    report_id: str,
    ticker: str,
    trade_date: str,
    record: DecisionRecord,
) -> dict[str, Any]:
    decision_id = _uuid("dec")
    with session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO trade_decisions
            (id, report_id, user_id, workspace_id, ticker, trade_date, rating,
             action, entry_price, stop_loss, price_target, position_pct,
             settlement_days, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')
            """,
            (
                decision_id,
                report_id,
                DEFAULT_USER_ID,
                DEFAULT_WORKSPACE_ID,
                ticker,
                trade_date,
                record.rating,
                record.action,
                record.entry_price,
                record.stop_loss,
                record.price_target,
                record.position_pct,
                record.settlement_days,
            ),
        )
        row = conn.execute(
            "SELECT * FROM trade_decisions WHERE id = ?", (decision_id,)
        ).fetchone()
    return _dict(row)


def get_decision_by_report(db_path: Path | str, report_id: str) -> dict[str, Any]:
    with session(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM trade_decisions WHERE report_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (report_id,),
        ).fetchone()
    return _dict(row)


def get_decision(db_path: Path | str, decision_id: str) -> dict[str, Any]:
    with session(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM trade_decisions WHERE id = ?", (decision_id,)
        ).fetchone()
    return _dict(row)


def update_decision(
    db_path: Path | str,
    decision_id: str,
    conn: sqlite3.Connection | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """更新决策字段。传入 conn 时在调用方事务内执行。"""
    allowed = {"status", "judge_json"}
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return get_decision(db_path, decision_id)

    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [decision_id]

    def _run(c: sqlite3.Connection) -> dict[str, Any]:
        c.execute(
            f"UPDATE trade_decisions SET {assignments} WHERE id = ?",
            values,
        )
        row = c.execute(
            "SELECT * FROM trade_decisions WHERE id = ?", (decision_id,)
        ).fetchone()
        return _dict(row)

    if conn is not None:
        return _run(conn)
    with session(db_path) as owned:
        return _run(owned)


def create_order(
    db_path: Path | str,
    decision_id: str,
    account_id: str,
    ticker: str,
    side: str,
    quantity: int,
    exec_date: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """创建 pending 订单。传入 conn 时在调用方事务内执行（下单+决策状态原子性）。"""
    order_id = _uuid("ord")

    def _run(c: sqlite3.Connection) -> dict[str, Any]:
        c.execute(
            """
            INSERT INTO trade_orders
            (id, decision_id, account_id, ticker, side, quantity, status, exec_date)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (order_id, decision_id, account_id, ticker, side, quantity, exec_date),
        )
        row = c.execute(
            "SELECT * FROM trade_orders WHERE id = ?", (order_id,)
        ).fetchone()
        return _dict(row)

    if conn is not None:
        return _run(conn)
    with session(db_path) as owned:
        return _run(owned)


def list_orders(
    db_path: Path | str,
    account_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM trade_orders"
    conditions, values = [], []
    if account_id:
        conditions.append("account_id = ?")
        values.append(account_id)
    if status:
        conditions.append("status = ?")
        values.append(status)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY created_at DESC, rowid DESC"
    with session(db_path) as conn:
        rows = conn.execute(sql, values).fetchall()
    return [_dict(row) for row in rows]


def list_orders_by_decision(db_path: Path | str, decision_id: str) -> list[dict[str, Any]]:
    with session(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM trade_orders WHERE decision_id = ? ORDER BY created_at ASC, rowid ASC",
            (decision_id,),
        ).fetchall()
    return [_dict(row) for row in rows]


def update_order(
    db_path: Path | str, order_id: str, conn: sqlite3.Connection | None = None, **fields: Any
) -> dict[str, Any]:
    """更新订单字段。传入 conn 时在调用方事务内执行（撮合+扣款原子性）。"""
    allowed = {"status", "exec_date", "fill_price", "fill_quantity", "fee_amount", "reject_reason"}
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        if conn is not None:
            row = conn.execute(
                "SELECT * FROM trade_orders WHERE id = ?", (order_id,)
            ).fetchone()
            return _dict(row)
        with session(db_path) as owned:
            row = owned.execute(
                "SELECT * FROM trade_orders WHERE id = ?", (order_id,)
            ).fetchone()
        return _dict(row)

    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [order_id]

    def _run(c: sqlite3.Connection) -> dict[str, Any]:
        c.execute(f"UPDATE trade_orders SET {assignments} WHERE id = ?", values)
        row = c.execute(
            "SELECT * FROM trade_orders WHERE id = ?", (order_id,)
        ).fetchone()
        return _dict(row)

    if conn is not None:
        return _run(conn)
    with session(db_path) as owned:
        return _run(owned)


def list_decisions(db_path: Path | str) -> list[dict[str, Any]]:
    with session(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM trade_decisions ORDER BY created_at DESC, rowid DESC"
        ).fetchall()
    return [_dict(row) for row in rows]


def get_latest_decision_by_ticker(db_path: Path | str, ticker: str) -> dict[str, Any]:
    """该 ticker 最新一条决策（监控取止损/目标价阈值用）。"""
    with session(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM trade_decisions WHERE ticker = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (ticker,),
        ).fetchone()
    return _dict(row)


def create_alert(
    db_path: Path | str,
    account_id: str,
    ticker: str,
    kind: str,
    price: float,
    threshold: float,
    message: str,
) -> dict[str, Any]:
    alert_id = _uuid("alert")
    with session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO trade_alerts
            (id, account_id, ticker, kind, price, threshold, message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (alert_id, account_id, ticker, kind, price, threshold, message),
        )
        row = conn.execute(
            "SELECT * FROM trade_alerts WHERE id = ?", (alert_id,)
        ).fetchone()
    return _dict(row)


def has_open_alert(db_path: Path | str, ticker: str, kind: str) -> bool:
    with session(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM trade_alerts WHERE ticker = ? AND kind = ? AND status = 'open' LIMIT 1",
            (ticker, kind),
        ).fetchone()
    return row is not None


def list_alerts(db_path: Path | str, status: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM trade_alerts"
    values: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        values.append(status)
    sql += " ORDER BY created_at DESC, rowid DESC"
    with session(db_path) as conn:
        rows = conn.execute(sql, values).fetchall()
    return [_dict(row) for row in rows]


def ack_alert(db_path: Path | str, alert_id: str) -> dict[str, Any]:
    with session(db_path) as conn:
        conn.execute(
            "UPDATE trade_alerts SET status = 'acked' WHERE id = ?", (alert_id,)
        )
        row = conn.execute(
            "SELECT * FROM trade_alerts WHERE id = ?", (alert_id,)
        ).fetchone()
    return _dict(row)


def list_latest_equity_snapshots(
    db_path: Path | str, account_id: str, limit: int = 2
) -> list[dict[str, Any]]:
    with session(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM account_equity WHERE account_id = ? ORDER BY date DESC, rowid DESC LIMIT ?",
            (account_id, limit),
        ).fetchall()
    return [_dict(row) for row in rows]


def get_account(db_path: Path | str, account_id: str) -> dict[str, Any]:
    with session(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM trading_accounts WHERE id = ?", (account_id,)
        ).fetchone()
    return _dict(row)


def adjust_account_cash(
    db_path: Path | str,
    account_id: str,
    delta: float,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """成交后调整账户现金（delta 为负表示买入支出）。传入 conn 时在调用方事务内执行。"""

    def _run(c: sqlite3.Connection) -> dict[str, Any]:
        c.execute(
            "UPDATE trading_accounts SET cash = cash + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (delta, account_id),
        )
        row = c.execute(
            "SELECT * FROM trading_accounts WHERE id = ?", (account_id,)
        ).fetchone()
        return _dict(row)

    if conn is not None:
        return _run(conn)
    with session(db_path) as owned:
        return _run(owned)


def create_settlement(
    db_path: Path | str,
    decision_id: str,
    settle_date: str,
    ref_price: float,
    settle_price: float,
    decision_return: float,
    benchmark_return: float | None,
    excess_return: float | None,
    outcome: str,
) -> dict[str, Any]:
    settlement_id = _uuid("stl")
    with session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO trade_settlements
            (id, decision_id, settle_date, ref_price, settle_price,
             decision_return, benchmark_return, excess_return, outcome)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                settlement_id,
                decision_id,
                settle_date,
                ref_price,
                settle_price,
                decision_return,
                benchmark_return,
                excess_return,
                outcome,
            ),
        )
        row = conn.execute(
            "SELECT * FROM trade_settlements WHERE id = ?", (settlement_id,)
        ).fetchone()
    return _dict(row)


def get_settlement_by_decision(db_path: Path | str, decision_id: str) -> dict[str, Any]:
    with session(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM trade_settlements WHERE decision_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (decision_id,),
        ).fetchone()
    return _dict(row)


def list_settlements(db_path: Path | str) -> list[dict[str, Any]]:
    with session(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM trade_settlements ORDER BY created_at DESC, rowid DESC"
        ).fetchall()
    return [_dict(row) for row in rows]


def upsert_equity_snapshot(
    db_path: Path | str,
    account_id: str,
    date: str,
    cash: float,
    market_value: float,
    total_equity: float,
) -> dict[str, Any]:
    with session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO account_equity (id, account_id, date, cash, market_value, total_equity)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id, date) DO UPDATE SET
                cash = excluded.cash,
                market_value = excluded.market_value,
                total_equity = excluded.total_equity
            """,
            (_uuid("eq"), account_id, date, cash, market_value, total_equity),
        )
        row = conn.execute(
            "SELECT * FROM account_equity WHERE account_id = ? AND date = ?",
            (account_id, date),
        ).fetchone()
    return _dict(row)


def list_equity_snapshots(db_path: Path | str, account_id: str) -> list[dict[str, Any]]:
    with session(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM account_equity WHERE account_id = ? ORDER BY date ASC, rowid ASC",
            (account_id,),
        ).fetchall()
    return [_dict(row) for row in rows]


def record_judge_call(
    db_path: Path | str,
    decision_id: str,
    judge_name: str,
    verdict: str,
    latency_ms: int,
    detail: dict[str, Any],
) -> dict[str, Any]:
    call_id = _uuid("judge")
    with session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO judge_calls
            (id, decision_id, judge_name, verdict, latency_ms, detail_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                call_id,
                decision_id,
                judge_name,
                verdict,
                latency_ms,
                json.dumps(detail, ensure_ascii=False),
            ),
        )
        row = conn.execute(
            "SELECT * FROM judge_calls WHERE id = ?", (call_id,)
        ).fetchone()
    saved = _dict(row)
    saved["detail_json"] = json.loads(saved["detail_json"])
    return saved


def list_judge_calls(db_path: Path | str, decision_id: str) -> list[dict[str, Any]]:
    with session(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM judge_calls WHERE decision_id = ? ORDER BY created_at ASC, rowid ASC",
            (decision_id,),
        ).fetchall()
    calls = [_dict(row) for row in rows]
    for call in calls:
        call["detail_json"] = json.loads(call["detail_json"])
    return calls
