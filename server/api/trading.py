"""Trading API routes：账户、决策、执行决策、订单。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from server.core.llm_config import build_research_config
from server.db.trading_repositories import (
    get_decision,
    get_or_create_default_account,
    list_decisions,
    list_equity_snapshots,
    list_orders,
    list_settlements,
)
from server.services.report_service import build_report_detail
from server.trading.judge import Judge, LLMJudge, RuleJudge
from server.trading.order_service import OrderError, OrderService, get_positions

router = APIRouter(prefix="/api/trading", tags=["trading"])


def _default_ref_price(ticker: str, trade_date: str) -> float | None:
    """决策日收盘价（用于 entry_price 缺失时的仓位换算）。"""
    try:
        from alphamind.dataflows.a_stock import _load_ohlcv_astock

        df = _load_ohlcv_astock(ticker, trade_date)
        if df is None or df.empty:
            return None
        return float(df.iloc[-1]["Close"])
    except Exception:
        return None


def build_default_judge() -> Judge:
    """v1 默认 quick-LLM Judge；LLM 不可用时降级规则 Judge。"""
    try:
        config = build_research_config()
        from alphamind.llm_clients.factory import create_llm_client

        client = create_llm_client(
            config["llm_provider"], config["quick_think_llm"], config.get("backend_url")
        )
        return LLMJudge(client.get_llm(), provider=config["llm_provider"])
    except Exception:
        return RuleJudge()


def _service(request: Request) -> OrderService:
    return OrderService(
        request.app.state.database_path,
        judge=build_default_judge(),
        ref_price_provider=_default_ref_price,
    )


@router.get("/account")
def account(request: Request) -> dict:
    db_path = request.app.state.database_path
    account = get_or_create_default_account(db_path)
    positions = get_positions(db_path, account["id"])
    return {
        "account": account,
        "positions": [
            {"ticker": ticker, **pos} for ticker, pos in positions.items()
        ],
        "orders": list_orders(db_path, account_id=account["id"]),
    }


@router.get("/decisions")
def decisions(request: Request) -> list[dict]:
    return list_decisions(request.app.state.database_path)


@router.post("/decisions/{decision_id}/execute")
def execute_decision(decision_id: str, request: Request) -> dict:
    db_path = request.app.state.database_path
    decision = get_decision(db_path, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    context: dict[str, Any] | None = None
    try:
        detail = build_report_detail(db_path, decision["report_id"])
        state = detail.get("state") or {}
        if isinstance(state, dict) and state.get("final_trade_decision"):
            context = {"pm_decision": str(state["final_trade_decision"])}
    except Exception:
        context = None

    try:
        return _service(request).execute_decision(decision_id, judge_context=context)
    except OrderError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/orders")
def orders(request: Request) -> list[dict]:
    db_path = request.app.state.database_path
    account = get_or_create_default_account(db_path)
    return list_orders(db_path, account_id=account["id"])


@router.post("/refresh")
def refresh(request: Request) -> dict:
    """一键刷新：撮合 pending 订单 → 结算到期决策 → 净值快照。"""
    from server.trading.broker import SimulatedBroker
    from server.trading.settlement import (
        astock_close_provider,
        astock_quote_provider,
        refresh as run_refresh,
        yfinance_benchmark_provider,
    )

    return run_refresh(
        request.app.state.database_path,
        broker=SimulatedBroker(astock_quote_provider),
        close_provider=astock_close_provider,
        benchmark_provider=yfinance_benchmark_provider,
    )


@router.get("/alerts")
def alerts(request: Request) -> list[dict]:
    """监控告警（默认返回未确认的，status=acked 可看历史）。"""
    from server.db.trading_repositories import list_alerts

    return list_alerts(request.app.state.database_path)


@router.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: str, request: Request) -> dict:
    from server.db.trading_repositories import ack_alert as ack

    alert = ack(request.app.state.database_path, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.get("/settlements")
def settlements(request: Request) -> list[dict]:
    return list_settlements(request.app.state.database_path)


@router.get("/equity")
def equity(request: Request) -> list[dict]:
    db_path = request.app.state.database_path
    account = get_or_create_default_account(db_path)
    return list_equity_snapshots(db_path, account["id"])
