"""持仓监控：最新收盘价 vs 决策的止损价/目标价，触发时生成告警。

数据源注入（CloseProvider），与 settlement 同一风格；告警去重靠
has_open_alert（同 ticker 同 kind 只保留一条 open），用户 ack 后可再次触发。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from server.db.trading_repositories import (
    create_alert,
    get_latest_decision_by_ticker,
    get_or_create_default_account,
    has_open_alert,
)
from server.trading.order_service import get_positions
from server.trading.settlement import CloseProvider

KIND_STOP_LOSS = "stop_loss_hit"
KIND_PRICE_TARGET = "price_target_hit"


def scan_position_alerts(
    db_path: Path | str,
    close_provider: CloseProvider,
    as_of: str,
) -> list[dict[str, Any]]:
    """扫描持仓：收盘价下破止损 → 止损告警；上达目标价 → 目标价告警。

    阈值取该 ticker 最新一条决策（通常即买入依据）；决策或行情
    缺失时跳过（下次 refresh 重试）。
    """
    account = get_or_create_default_account(db_path)
    positions = get_positions(db_path, account["id"])
    triggered: list[dict[str, Any]] = []

    for ticker, _pos in positions.items():
        decision = get_latest_decision_by_ticker(db_path, ticker)
        if not decision:
            continue
        price = close_provider(ticker, as_of)
        if price is None:
            continue

        stop_loss = decision.get("stop_loss")
        target = decision.get("price_target")

        if stop_loss and price <= float(stop_loss):
            if not has_open_alert(db_path, ticker, KIND_STOP_LOSS):
                triggered.append(
                    create_alert(
                        db_path,
                        account_id=account["id"],
                        ticker=ticker,
                        kind=KIND_STOP_LOSS,
                        price=price,
                        threshold=float(stop_loss),
                        message=f"{ticker} 收盘价 {price:.2f} 已跌破止损价 {float(stop_loss):.2f}，请检查持仓",
                    )
                )
        if target and price >= float(target):
            if not has_open_alert(db_path, ticker, KIND_PRICE_TARGET):
                triggered.append(
                    create_alert(
                        db_path,
                        account_id=account["id"],
                        ticker=ticker,
                        kind=KIND_PRICE_TARGET,
                        price=price,
                        threshold=float(target),
                        message=f"{ticker} 收盘价 {price:.2f} 已达目标价 {float(target):.2f}，可考虑减仓",
                    )
                )
    return triggered
