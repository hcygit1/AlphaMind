"""结算与账户刷新：pending 订单撮合、T+N 结算 vs 沪深300、净值快照。

数据源全部注入（CloseProvider / BenchmarkProvider），默认实现基于
alphamind 日线缓存与 yfinance 沪深300，异常一律容忍（返回 None 跳过，
下次 refresh 重试）。
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from server.db.connection import session
from server.db.trading_repositories import (
    adjust_account_cash,
    create_settlement,
    get_decision,
    get_or_create_default_account,
    get_settlement_by_decision,
    list_decisions,
    list_orders,
    list_orders_by_decision,
    update_decision,
    update_order,
    upsert_equity_snapshot,
)
from server.trading.broker import (
    STATUS_FILLED,
    STATUS_PENDING,
    STATUS_REJECTED,
    SimulatedBroker,
)
from server.trading.order_service import get_positions, next_business_day

# close_provider(ticker, date) -> date 当日或之前最近收盘价 | None
CloseProvider = Callable[[str, str], float | None]
# benchmark_close(start_date, end_date) -> (start_close, end_close) | None
BenchmarkProvider = Callable[[str, str], tuple[float, float] | None]

# pending 订单 exec_date 顺延上限（工作日），超过则取消
MAX_ORDER_DELAY_WORKDAYS = 15

# refresh 全程互斥：并发两个 refresh 会读到同一批 pending 订单导致重复成交/双重扣款
_refresh_lock = threading.Lock()


def process_pending_orders(
    db_path: Path | str, broker: SimulatedBroker, as_of: str | None = None
) -> dict[str, int]:
    """扫描 pending 订单：成交 → 更新订单与现金；拒单 → 落原因；
    数据未到 → exec_date 顺延一个工作日，长期无数据取消。"""
    stats = {"filled": 0, "rejected": 0, "postponed": 0, "cancelled": 0}
    for order in list_orders(db_path, status="pending"):
        fill = broker.try_fill(
            order["ticker"], order["side"], int(order["quantity"]), str(order["exec_date"])
        )
        if fill.status == STATUS_FILLED:
            # 单事务保证原子性：订单状态与账户现金要么同时生效，要么同时回滚，
            # 避免中途崩溃出现「已成交但钱没扣」的账目错乱
            with session(db_path) as conn:
                update_order(
                    db_path,
                    order["id"],
                    conn=conn,
                    status=STATUS_FILLED,
                    fill_price=fill.fill_price,
                    fill_quantity=fill.fill_quantity,
                    fee_amount=fill.fee_amount,
                )
                amount = fill.fill_price * fill.fill_quantity
                delta = (
                    -amount - fill.fee_amount
                    if order["side"] == "buy"
                    else amount - fill.fee_amount
                )
                adjust_account_cash(db_path, order["account_id"], round(delta, 2), conn=conn)
            stats["filled"] += 1
        elif fill.status == STATUS_REJECTED:
            update_order(db_path, order["id"], status=STATUS_REJECTED, reject_reason=fill.reject_reason)
            stats["rejected"] += 1
        else:  # 行情未到
            new_date = next_business_day(str(order["exec_date"]))
            decision = get_decision(db_path, order["decision_id"])
            anchor = str(decision["trade_date"]) if decision else str(order["exec_date"])
            if _business_days_between(anchor, new_date) > MAX_ORDER_DELAY_WORKDAYS:
                update_order(
                    db_path, order["id"], status="cancelled", reject_reason="行情数据长期缺失"
                )
                stats["cancelled"] += 1
            else:
                update_order(db_path, order["id"], exec_date=new_date)
                stats["postponed"] += 1
    return stats


def settle_due_decisions(
    db_path: Path | str,
    as_of: str,
    close_provider: CloseProvider,
    benchmark_provider: BenchmarkProvider | None = None,
) -> list[dict[str, Any]]:
    """结算到期决策：settle_date = trade_date + settlement_days 个工作日。

    - ref_price 取订单实际成交价；无成交订单的决策跳过（等待或拒单）
    - decision_return：买入 = settle/ref-1，卖出 = 1-settle/ref
    - benchmark_return：沪深300 同期（exec_date → settle_date）
    - 幂等：已有 settlement 的决策跳过
    """
    settled: list[dict[str, Any]] = []
    for decision in list_decisions(db_path):
        if decision["status"] != "executed":
            continue
        if get_settlement_by_decision(db_path, decision["id"]):
            continue

        orders = [
            o for o in list_orders_by_decision(db_path, decision["id"]) if o["status"] == STATUS_FILLED
        ]
        if not orders:
            continue

        settle_date = _add_business_days(
            str(decision["trade_date"]), int(decision["settlement_days"])
        )
        if settle_date > as_of:
            continue
        settle_price = close_provider(decision["ticker"], settle_date)
        if settle_price is None:
            continue

        order = orders[0]  # v1 一条决策一单
        ref_price = float(order["fill_price"])
        if order["side"] == "buy":
            decision_return = settle_price / ref_price - 1
        else:
            decision_return = 1 - settle_price / ref_price

        benchmark_return = None
        if benchmark_provider:
            pair = benchmark_provider(str(order["exec_date"]), settle_date)
            if pair and pair[0] > 0:
                benchmark_return = pair[1] / pair[0] - 1
        excess = (
            decision_return - benchmark_return if benchmark_return is not None else None
        )
        outcome = _outcome_text(decision_return, excess)

        settlement = create_settlement(
            db_path,
            decision_id=decision["id"],
            settle_date=settle_date,
            ref_price=ref_price,
            settle_price=settle_price,
            decision_return=round(decision_return, 6),
            benchmark_return=None if benchmark_return is None else round(benchmark_return, 6),
            excess_return=None if excess is None else round(excess, 6),
            outcome=outcome,
        )
        update_decision(db_path, decision["id"], status="settled")
        settled.append(settlement)
    return settled


def snapshot_equity(
    db_path: Path | str, as_of: str, close_provider: CloseProvider
) -> dict[str, Any]:
    """现金 + 持仓市值（最新收盘价）→ account_equity 快照（UPSERT）。"""
    account = get_or_create_default_account(db_path)
    positions = get_positions(db_path, account["id"])
    market_value = 0.0
    for ticker, pos in positions.items():
        price = close_provider(ticker, as_of)
        if price:
            market_value += int(pos["quantity"]) * float(price)
    cash = float(account["cash"])
    return upsert_equity_snapshot(
        db_path,
        account_id=account["id"],
        date=as_of,
        cash=round(cash, 2),
        market_value=round(market_value, 2),
        total_equity=round(cash + market_value, 2),
    )


def refresh(
    db_path: Path | str,
    broker: SimulatedBroker,
    close_provider: CloseProvider,
    benchmark_provider: BenchmarkProvider | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """一键刷新：撮合 pending 订单 → 结算到期决策 → 净值快照 → 持仓监控。

    全程持互斥锁；已有 refresh 在跑时立即返回 busy，避免重复成交。
    """
    if not _refresh_lock.acquire(blocking=False):
        return {"status": "busy", "detail": "已有刷新任务在执行，请稍后再试"}
    try:
        return _refresh_locked(db_path, broker, close_provider, benchmark_provider, as_of)
    finally:
        _refresh_lock.release()


def _refresh_locked(
    db_path: Path | str,
    broker: SimulatedBroker,
    close_provider: CloseProvider,
    benchmark_provider: BenchmarkProvider | None,
    as_of: str | None,
) -> dict[str, Any]:
    as_of = as_of or str(pd.Timestamp.now().date())
    order_stats = process_pending_orders(db_path, broker, as_of=as_of)
    settlements = settle_due_decisions(db_path, as_of, close_provider, benchmark_provider)
    equity = snapshot_equity(db_path, as_of, close_provider)

    from server.trading.monitoring import scan_position_alerts

    alerts = scan_position_alerts(db_path, close_provider, as_of)
    return {
        "orders": order_stats,
        "settlements": settlements,
        "equity": equity,
        "alerts": alerts,
    }


# ---- 工具 ----


def _add_business_days(date_str: str, n: int) -> str:
    ts = pd.Timestamp(date_str)
    return str((ts + n * pd.tseries.offsets.BDay(1)).date())


def _business_days_between(start: str, end: str) -> int:
    return int(
        len(pd.bdate_range(pd.Timestamp(start), pd.Timestamp(end))) - 1
    )


def _outcome_text(decision_return: float, excess: float | None) -> str:
    if excess is None:
        return "盈利" if decision_return > 0 else ("亏损" if decision_return < 0 else "持平")
    if excess > 0:
        return "跑赢基准"
    if excess < 0:
        return "跑输基准"
    return "持平"


# ---- 默认数据源（可被注入替换） ----


def astock_quote_provider(exec_date: str, ticker: str) -> dict | None:
    """exec_date 日线构造 broker 行情：开盘价 + 按板块规则的涨跌停近似。"""
    try:
        from alphamind.dataflows.a_stock import _load_ohlcv_astock, _normalize_ticker

        code = _normalize_ticker(ticker)
        df = _load_ohlcv_astock(code, exec_date)
        if df is None or df.empty:
            return None
        dates = df["Date"].dt.strftime("%Y-%m-%d")
        if not (dates == exec_date).any():
            return None
        open_price = float(df.loc[dates == exec_date, "Open"].iloc[0])
        prev = df[dates < exec_date]
        if prev.empty:
            return {"open": open_price, "limit_up": None, "limit_down": None}
        prev_close = float(prev["Close"].iloc[-1])
        pct = _limit_pct(code)
        return {
            "open": open_price,
            "limit_up": round(prev_close * (1 + pct), 2),
            "limit_down": round(prev_close * (1 - pct), 2),
        }
    except Exception:
        return None


def _limit_pct(code: str) -> float:
    """涨跌停幅度近似：创业板/科创板 20%，北交所 30%，主板 10%（ST 不可识别）。"""
    if code.startswith(("300", "301", "688")):
        return 0.20
    if code.startswith(("8", "4")):
        return 0.30
    return 0.10


def astock_close_provider(ticker: str, date: str) -> float | None:
    """date 当日或之前最近收盘价。"""
    try:
        from alphamind.dataflows.a_stock import _load_ohlcv_astock, _normalize_ticker

        df = _load_ohlcv_astock(_normalize_ticker(ticker), date)
        if df is None or df.empty:
            return None
        return float(df.iloc[-1]["Close"])
    except Exception:
        return None


def yfinance_benchmark_provider(start: str, end: str) -> tuple[float, float] | None:
    """沪深300（000300.SS）区间首尾收盘。"""
    try:
        import yfinance as yf

        hist = yf.Ticker("000300.SS").history(start=start, end=_add_one_day(end))
        if hist is None or len(hist) < 1:
            return None
        first = float(hist["Close"].iloc[0])
        last = float(hist["Close"].iloc[-1])
        return (first, last)
    except Exception:
        return None


def _add_one_day(date_str: str) -> str:
    return str((pd.Timestamp(date_str) + pd.Timedelta(days=1)).date())
