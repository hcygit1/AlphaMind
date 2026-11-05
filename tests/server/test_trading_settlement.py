"""结算模块测试：pending 撮合、T+N 结算 vs 基准、净值快照、refresh 集成。"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.db.connection import init_db
from server.db.repositories import upsert_default_identity, upsert_report
from server.db.trading_repositories import (
    create_decision,
    create_order,
    get_account,
    get_decision,
    get_or_create_default_account,
    get_settlement_by_decision,
    list_equity_snapshots,
    update_decision,
    update_order,
)
from server.trading.broker import SimulatedBroker
from server.trading.extraction import DecisionRecord
from server.trading.order_service import next_business_day
from server.trading.settlement import (
    process_pending_orders,
    refresh,
    settle_due_decisions,
    snapshot_equity,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.sqlite3"
    init_db(path)
    upsert_default_identity(path)
    return path


def _decision(db_path, trade_date="2026-01-05", rating="Buy", action="Buy", settlement_days=5):
    report = upsert_report(
        db_path, ticker="600000", trade_date=trade_date, signal=rating,
        summary="s", state_path="/tmp/state.json",
    )
    return create_decision(
        db_path, report_id=report["id"], ticker="600000", trade_date=trade_date,
        record=DecisionRecord(rating=rating, action=action, settlement_days=settlement_days),
    )


def _pending_order(db_path, decision, side="buy", quantity=1000, exec_date=None):
    # 真实流程中 execute_decision 建 pending 订单时即置 executed
    update_decision(db_path, decision["id"], status="executed")
    account = get_or_create_default_account(db_path)
    return create_order(
        db_path, decision_id=decision["id"], account_id=account["id"],
        ticker="600000", side=side, quantity=quantity,
        exec_date=exec_date or next_business_day(decision["trade_date"]),
    )


def _filled_order(db_path, decision, side, quantity, price, exec_date, fee=5.0):
    order = _pending_order(db_path, decision, side=side, quantity=quantity, exec_date=exec_date)
    return update_order(
        db_path, order["id"], status="filled",
        fill_price=price, fill_quantity=quantity, fee_amount=fee,
    )


def _broker(quotes: dict):
    """quotes: {(date, ticker): {open, limit_up, limit_down} | None}。"""
    return SimulatedBroker(lambda d, t: quotes.get((d, t)))


class TestProcessPendingOrders:
    def test_fill_updates_order_and_cash(self, db_path):
        decision = _decision(db_path)
        _pending_order(db_path, decision, quantity=1000)  # exec 2026-01-06
        account_id = get_or_create_default_account(db_path)["id"]

        broker = _broker({("2026-01-06", "600000"): {"open": 10.0, "limit_up": 11.0, "limit_down": 9.0}})
        stats = process_pending_orders(db_path, broker)
        assert stats == {"filled": 1, "rejected": 0, "postponed": 0, "cancelled": 0}

        account = get_account(db_path, account_id)
        assert account["cash"] == pytest.approx(1_000_000 - 10_000 - 5)

    def test_sell_fill_adds_cash(self, db_path):
        decision = _decision(db_path, rating="Sell", action="Sell")
        _pending_order(db_path, decision, side="sell", quantity=1000)
        account_id = get_or_create_default_account(db_path)["id"]

        broker = _broker({("2026-01-06", "600000"): {"open": 10.0, "limit_up": 11.0, "limit_down": 9.0}})
        process_pending_orders(db_path, broker)
        account = get_account(db_path, account_id)
        # 卖出：佣金 5 + 印花税 10
        assert account["cash"] == pytest.approx(1_000_000 + 10_000 - 15)

    def test_reject_records_reason(self, db_path):
        decision = _decision(db_path)
        order = _pending_order(db_path, decision)

        broker = _broker({("2026-01-06", "600000"): {"open": 11.0, "limit_up": 11.0, "limit_down": 9.0}})
        stats = process_pending_orders(db_path, broker)
        assert stats["rejected"] == 1

        from server.db.trading_repositories import list_orders

        saved = [o for o in list_orders(db_path) if o["id"] == order["id"]][0]
        assert saved["status"] == "rejected"
        assert "涨停" in saved["reject_reason"]

    def test_postpones_when_no_data(self, db_path):
        decision = _decision(db_path)
        order = _pending_order(db_path, decision, exec_date="2026-01-06")

        stats = process_pending_orders(db_path, _broker({}))
        assert stats["postponed"] == 1

        from server.db.trading_repositories import list_orders

        saved = [o for o in list_orders(db_path) if o["id"] == order["id"]][0]
        assert saved["exec_date"] == "2026-01-07"  # 顺延一个工作日
        assert saved["status"] == "pending"

    def test_cancels_after_long_delay(self, db_path):
        # trade_date 距 exec_date 已超 15 个工作日
        decision = _decision(db_path, trade_date="2025-11-01")
        order = _pending_order(db_path, decision, exec_date="2026-01-06")

        stats = process_pending_orders(db_path, _broker({}))
        assert stats["cancelled"] == 1

        from server.db.trading_repositories import list_orders

        saved = [o for o in list_orders(db_path) if o["id"] == order["id"]][0]
        assert saved["status"] == "cancelled"


class TestSettleDueDecisions:
    def test_buy_settlement_with_benchmark(self, db_path):
        decision = _decision(db_path, settlement_days=5)  # settle 2026-01-12
        _filled_order(db_path, decision, "buy", 1000, 10.0, "2026-01-06")

        # 结算价 12 → 收益 20%；基准 100→105 → 5%；超额 15%
        settlements = settle_due_decisions(
            db_path, "2026-01-12",
            close_provider=lambda t, d: 12.0 if d >= "2026-01-12" else 10.0,
            benchmark_provider=lambda s, e: (100.0, 105.0),
        )
        assert len(settlements) == 1
        s = settlements[0]
        assert s["ref_price"] == 10.0
        assert s["settle_price"] == 12.0
        assert s["decision_return"] == pytest.approx(0.2)
        assert s["benchmark_return"] == pytest.approx(0.05)
        assert s["excess_return"] == pytest.approx(0.15)
        assert s["outcome"] == "跑赢基准"
        assert get_decision(db_path, decision["id"])["status"] == "settled"

    def test_sell_settlement_return_inverted(self, db_path):
        decision = _decision(db_path, rating="Sell", action="Sell", settlement_days=5)
        _filled_order(db_path, decision, "sell", 1000, 10.0, "2026-01-06")

        # 卖出后涨到 11 → 亏损 10%
        settlements = settle_due_decisions(
            db_path, "2026-01-12",
            close_provider=lambda t, d: 11.0,
            benchmark_provider=None,
        )
        assert settlements[0]["decision_return"] == pytest.approx(-0.1)
        assert settlements[0]["excess_return"] is None
        assert settlements[0]["outcome"] == "亏损"

    def test_idempotent(self, db_path):
        decision = _decision(db_path, settlement_days=5)
        _filled_order(db_path, decision, "buy", 1000, 10.0, "2026-01-06")

        provider = lambda t, d: 12.0
        settle_due_decisions(db_path, "2026-01-12", close_provider=provider)
        second = settle_due_decisions(db_path, "2026-01-12", close_provider=provider)
        assert second == []
        assert get_settlement_by_decision(db_path, decision["id"])["settle_price"] == 12.0

    def test_skips_when_not_due(self, db_path):
        decision = _decision(db_path, settlement_days=20)
        _filled_order(db_path, decision, "buy", 1000, 10.0, "2026-01-06")

        settlements = settle_due_decisions(db_path, "2026-01-12", close_provider=lambda t, d: 12.0)
        assert settlements == []

    def test_skips_when_no_filled_order(self, db_path):
        decision = _decision(db_path, settlement_days=5)
        _pending_order(db_path, decision)  # 仍 pending

        settlements = settle_due_decisions(db_path, "2026-01-20", close_provider=lambda t, d: 12.0)
        assert settlements == []

    def test_settled_decision_not_reprocessed(self, db_path):
        # status 已是 settled 的决策不重复处理（幂等的另一面）
        decision = _decision(db_path, settlement_days=5)
        _filled_order(db_path, decision, "buy", 1000, 10.0, "2026-01-06")
        update_decision(db_path, decision["id"], status="settled")

        settlements = settle_due_decisions(db_path, "2026-01-12", close_provider=lambda t, d: 12.0)
        assert settlements == []


class TestSnapshotEquity:
    def test_snapshot_cash_plus_market_value(self, db_path):
        decision = _decision(db_path)
        _filled_order(db_path, decision, "buy", 1000, 10.0, "2026-01-06")
        # 手动扣现金（模拟已成交）
        from server.db.trading_repositories import adjust_account_cash

        adjust_account_cash(db_path, get_or_create_default_account(db_path)["id"], -10_005)

        snapshot = snapshot_equity(db_path, "2026-01-07", close_provider=lambda t, d: 12.0)
        assert snapshot["cash"] == pytest.approx(989_995)
        assert snapshot["market_value"] == pytest.approx(12_000)
        assert snapshot["total_equity"] == pytest.approx(1_001_995)

    def test_snapshot_upserts_same_date(self, db_path):
        snapshot_equity(db_path, "2026-01-07", close_provider=lambda t, d: 12.0)
        snapshot_equity(db_path, "2026-01-07", close_provider=lambda t, d: 13.0)
        snapshots = list_equity_snapshots(db_path, get_or_create_default_account(db_path)["id"])
        assert len(snapshots) == 1

    def test_missing_price_counts_zero(self, db_path):
        decision = _decision(db_path)
        _filled_order(db_path, decision, "buy", 1000, 10.0, "2026-01-06")
        snapshot = snapshot_equity(db_path, "2026-01-07", close_provider=lambda t, d: None)
        assert snapshot["market_value"] == 0


class TestRefresh:
    def test_end_to_end(self, db_path):
        decision = _decision(db_path, settlement_days=5)
        _pending_order(db_path, decision, quantity=1000)  # exec 2026-01-06

        broker = _broker({("2026-01-06", "600000"): {"open": 10.0, "limit_up": 11.0, "limit_down": 9.0}})
        result = refresh(
            db_path, broker,
            close_provider=lambda t, d: 11.0,
            benchmark_provider=lambda s, e: (100.0, 102.0),
            as_of="2026-01-12",
        )
        assert result["orders"] == {"filled": 1, "rejected": 0, "postponed": 0, "cancelled": 0}
        assert len(result["settlements"]) == 1
        # 净值 = 现金 989995 + 1000 × 11 = 1_000_995
        assert result["equity"]["total_equity"] == pytest.approx(1_000_995)
