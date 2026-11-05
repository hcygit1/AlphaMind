"""持仓监控测试：止损/目标价告警触发、去重、ack 后重新触发、refresh 集成。"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.db.connection import init_db
from server.db.repositories import upsert_default_identity, upsert_report
from server.db.trading_repositories import (
    ack_alert,
    create_decision,
    create_order,
    get_or_create_default_account,
    list_alerts,
    update_decision,
    update_order,
)
from server.trading.broker import SimulatedBroker
from server.trading.extraction import DecisionRecord
from server.trading.monitoring import KIND_PRICE_TARGET, KIND_STOP_LOSS, scan_position_alerts
from server.trading.order_service import next_business_day
from server.trading.settlement import refresh


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.sqlite3"
    init_db(path)
    upsert_default_identity(path)
    return path


def _decision(db_path, stop_loss=9.5, price_target=12.0, ticker="600000", trade_date="2026-01-05"):
    report = upsert_report(
        db_path, ticker=ticker, trade_date=trade_date, signal="Buy",
        summary="s", state_path="/tmp/state.json",
    )
    return create_decision(
        db_path, report_id=report["id"], ticker=ticker, trade_date=trade_date,
        record=DecisionRecord(
            rating="Buy", action="Buy", stop_loss=stop_loss, price_target=price_target
        ),
    )


def _position(db_path, decision, ticker="600000", quantity=1000, price=10.0):
    """造一笔已成交买入 → 形成持仓。"""
    update_decision(db_path, decision["id"], status="executed")
    account_id = get_or_create_default_account(db_path)["id"]
    order = create_order(
        db_path, decision_id=decision["id"], account_id=account_id,
        ticker=ticker, side="buy", quantity=quantity,
        exec_date=next_business_day(decision["trade_date"]),
    )
    return update_order(
        db_path, order["id"], status="filled",
        fill_price=price, fill_quantity=quantity, fee_amount=5.0,
    )


class TestScanPositionAlerts:
    def test_stop_loss_triggered(self, db_path):
        decision = _decision(db_path, stop_loss=9.5)
        _position(db_path, decision)

        alerts = scan_position_alerts(db_path, lambda t, d: 9.0, as_of="2026-01-12")
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["ticker"] == "600000"
        assert alert["kind"] == KIND_STOP_LOSS
        assert alert["price"] == 9.0
        assert alert["threshold"] == 9.5
        assert "跌破止损价" in alert["message"]
        assert alert["status"] == "open"

    def test_price_target_triggered(self, db_path):
        decision = _decision(db_path, price_target=12.0)
        _position(db_path, decision)

        alerts = scan_position_alerts(db_path, lambda t, d: 12.5, as_of="2026-01-12")
        assert len(alerts) == 1
        assert alerts[0]["kind"] == KIND_PRICE_TARGET
        assert "已达目标价" in alerts[0]["message"]

    def test_within_range_no_alert(self, db_path):
        decision = _decision(db_path, stop_loss=9.5, price_target=12.0)
        _position(db_path, decision)

        alerts = scan_position_alerts(db_path, lambda t, d: 10.5, as_of="2026-01-12")
        assert alerts == []

    def test_dedup_while_open(self, db_path):
        decision = _decision(db_path, stop_loss=9.5)
        _position(db_path, decision)
        provider = lambda t, d: 9.0

        first = scan_position_alerts(db_path, provider, as_of="2026-01-12")
        second = scan_position_alerts(db_path, provider, as_of="2026-01-13")
        assert len(first) == 1
        assert second == []  # 已有 open 告警，不重复
        assert len(list_alerts(db_path)) == 1

    def test_ack_allows_retrigger(self, db_path):
        decision = _decision(db_path, stop_loss=9.5)
        _position(db_path, decision)
        provider = lambda t, d: 9.0

        alert = scan_position_alerts(db_path, provider, as_of="2026-01-12")[0]
        ack_alert(db_path, alert["id"])

        retriggered = scan_position_alerts(db_path, provider, as_of="2026-01-13")
        assert len(retriggered) == 1
        assert retriggered[0]["id"] != alert["id"]

    def test_missing_price_skipped(self, db_path):
        decision = _decision(db_path, stop_loss=9.5)
        _position(db_path, decision)

        assert scan_position_alerts(db_path, lambda t, d: None, as_of="2026-01-12") == []

    def test_position_without_decision_skipped(self, db_path):
        # 持仓对应的 ticker 没有任何决策（理论上少见，防御性跳过）
        decision = _decision(db_path, ticker="600000")
        _position(db_path, decision, ticker="600000")
        # 造第二个 ticker 的持仓：复用同一决策（ticker 不同）仅用于建 order
        account_id = get_or_create_default_account(db_path)["id"]
        order = create_order(
            db_path, decision_id=decision["id"], account_id=account_id,
            ticker="600519", side="buy", quantity=100, exec_date="2026-01-06",
        )
        update_order(db_path, order["id"], status="filled", fill_price=10.0, fill_quantity=100, fee_amount=5.0)

        # 600519 无决策 → 跳过；600000 决策的 stop_loss 是 9.5，价格 10.5 不触发
        alerts = scan_position_alerts(db_path, lambda t, d: 10.5, as_of="2026-01-12")
        assert alerts == []


class TestRefreshIntegration:
    def test_refresh_returns_alerts(self, db_path):
        decision = _decision(db_path, stop_loss=9.5, price_target=12.0)
        update_decision(db_path, decision["id"], status="executed")
        account_id = get_or_create_default_account(db_path)["id"]
        create_order(  # exec 2026-01-06
            db_path, decision_id=decision["id"], account_id=account_id,
            ticker="600000", side="buy", quantity=1000,
            exec_date=next_business_day(decision["trade_date"]),
        )

        broker = SimulatedBroker(
            lambda d, t: {"open": 10.0, "limit_up": 11.0, "limit_down": 9.0}
            if (d, t) == ("2026-01-06", "600000") else None
        )
        # 撮合成交（开盘 10）→ 持仓 600000；结算日收盘 9.0 跌破止损 9.5
        result = refresh(
            db_path, broker,
            close_provider=lambda t, d: 9.0,
            benchmark_provider=lambda s, e: (100.0, 102.0),
            as_of="2026-01-12",
        )
        assert result["orders"]["filled"] == 1
        assert len(result["alerts"]) == 1
        assert result["alerts"][0]["kind"] == KIND_STOP_LOSS
