"""OrderService 测试：方向推导、持仓推导、护栏、幂等、Judge 拦截。"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.db.connection import init_db
from server.db.repositories import upsert_default_identity, upsert_report
from server.db.trading_repositories import (
    create_decision,
    create_order,
    get_or_create_default_account,
    list_judge_calls,
    list_orders,
    update_order,
)
from server.trading.extraction import DecisionRecord
from server.trading.judge import VERDICT_BLOCK, VERDICT_PASS, Judge, JudgeResult
from server.trading.order_service import (
    OrderError,
    OrderService,
    get_positions,
    next_business_day,
    resolve_direction,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.sqlite3"
    init_db(path)
    upsert_default_identity(path)
    return path


class StubJudge(Judge):
    """固定 verdict 的测试替身。"""

    name = "stub"

    def __init__(self, verdict: str, message: str = "test"):
        self.verdict = verdict
        self.message = message

    def evaluate(self, decision, context=None) -> JudgeResult:
        checks = [{"severity": self.verdict, "message": self.message}] if self.verdict != VERDICT_PASS else []
        return JudgeResult(
            judge_name=self.name, verdict=self.verdict, checks=checks, latency_ms=1, provider="stub"
        )


def _report_id(db_path, ticker="600000") -> str:
    return upsert_report(
        db_path, ticker=ticker, trade_date="2026-01-05", signal="Buy",
        summary="s", state_path="/tmp/state.json",
    )["id"]


def _decision(db_path, ticker="600000", trade_date="2026-01-05", **kwargs) -> dict:
    defaults = dict(
        rating="Buy",
        action="Buy",
        entry_price=10.0,
        stop_loss=9.0,
        price_target=12.0,
        position_pct=0.10,
        settlement_days=20,
    )
    defaults.update(kwargs)
    report_id = _report_id(db_path, ticker)
    return create_decision(db_path, report_id=report_id, ticker=ticker, trade_date=trade_date, record=DecisionRecord(**defaults))


def _filled_order(db_path, account_id, ticker, side, quantity, price, exec_date, fee=5.0):
    decision = create_decision(
        db_path,
        report_id=_report_id(db_path, ticker),
        ticker=ticker,
        trade_date=exec_date,
        record=DecisionRecord(rating="Buy" if side == "buy" else "Sell", action="Buy" if side == "buy" else "Sell"),
    )
    order = create_order(
        db_path,
        decision_id=decision["id"],
        account_id=account_id,
        ticker=ticker,
        side=side,
        quantity=quantity,
        exec_date=exec_date,
    )
    return update_order(
        db_path,
        order["id"],
        status="filled",
        fill_price=price,
        fill_quantity=quantity,
        fee_amount=fee,
    )


def _insert_equity(db_path, account_id, date, total_equity):
    from server.db.connection import connect

    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO account_equity (account_id, date, cash, market_value, total_equity) VALUES (?, ?, 0, 0, ?)",
            (account_id, date, total_equity),
        )


class TestResolveDirection:
    def test_action_takes_priority(self):
        assert resolve_direction({"action": "Sell", "rating": "Buy"}) == "sell"

    def test_rating_fallback(self):
        assert resolve_direction({"action": None, "rating": "Sell"}) == "sell"
        assert resolve_direction({"action": None, "rating": "Overweight"}) == "buy"

    def test_hold_returns_none(self):
        assert resolve_direction({"action": "Hold", "rating": "Buy"}) is None
        assert resolve_direction({"action": None, "rating": "Hold"}) is None
        assert resolve_direction({"action": None, "rating": "unknown"}) is None


class TestNextBusinessDay:
    def test_skips_weekend(self):
        assert next_business_day("2026-01-09") == "2026-01-12"  # 周五 → 周一

    def test_midweek(self):
        assert next_business_day("2026-01-07") == "2026-01-08"  # 周三 → 周四


class TestGetPositions:
    def test_accumulates_buys_with_cost(self, db_path):
        account = get_or_create_default_account(db_path)
        _filled_order(db_path, account["id"], "600000", "buy", 1000, 10.0, "2026-01-05")
        _filled_order(db_path, account["id"], "600000", "buy", 1000, 12.0, "2026-01-06")

        positions = get_positions(db_path, account["id"])
        pos = positions["600000"]
        assert pos["quantity"] == 2000
        assert pos["avg_cost"] == pytest.approx((1000 * 10 + 5 + 1000 * 12 + 5) / 2000)

    def test_sell_reduces_quantity_keeps_avg_cost(self, db_path):
        account = get_or_create_default_account(db_path)
        _filled_order(db_path, account["id"], "600000", "buy", 1000, 10.0, "2026-01-05")
        _filled_order(db_path, account["id"], "600000", "sell", 500, 11.0, "2026-01-08", fee=10.0)

        positions = get_positions(db_path, account["id"])
        pos = positions["600000"]
        assert pos["quantity"] == 500
        assert pos["avg_cost"] == pytest.approx(10.005)  # 卖出不改持仓均价

    def test_t_plus_1_available(self, db_path):
        account = get_or_create_default_account(db_path)
        _filled_order(db_path, account["id"], "600000", "buy", 1000, 10.0, "2026-01-05")

        # exec_date 当日买入不可卖
        assert get_positions(db_path, account["id"], as_of="2026-01-05")["600000"]["available"] == 0
        # 次日可卖
        assert get_positions(db_path, account["id"], as_of="2026-01-06")["600000"]["available"] == 1000

    def test_empty_positions(self, db_path):
        account = get_or_create_default_account(db_path)
        assert get_positions(db_path, account["id"]) == {}


class TestExecuteDecision:
    def test_missing_decision_raises(self, db_path):
        service = OrderService(db_path)
        with pytest.raises(OrderError):
            service.execute_decision("dec_missing")

    def test_hold_skips(self, db_path):
        decision = _decision(db_path, rating="Hold", action="Hold", position_pct=None)
        result = OrderService(db_path).execute_decision(decision["id"])
        assert result["status"] == "skipped"
        assert list_orders(db_path) == []

    def test_buy_creates_pending_order(self, db_path):
        decision = _decision(db_path, entry_price=10.0, position_pct=0.10)
        result = OrderService(db_path).execute_decision(decision["id"])
        assert result["status"] == "executed"
        order = result["order"]
        assert order["side"] == "buy"
        assert order["quantity"] == 10000  # 100 万 × 10% / 10 元
        assert order["status"] == "pending"
        assert order["exec_date"] == "2026-01-06"  # 周一 T+1
        assert order["ticker"] == "600000"

    def test_position_pct_capped_at_max(self, db_path):
        decision = _decision(db_path, entry_price=10.0, position_pct=0.5)
        result = OrderService(db_path).execute_decision(decision["id"])
        # 100 万 × 20% / 10 元 = 20000 股
        assert result["order"]["quantity"] == 20000

    def test_default_pct_by_rating(self, db_path):
        decision = _decision(db_path, rating="Overweight", action="Buy", position_pct=None)
        result = OrderService(db_path).execute_decision(decision["id"])
        # Overweight 默认 5% → 100 万 × 5% / 10 = 5000 股
        assert result["order"]["quantity"] == 5000

    def test_idempotent_when_already_executed(self, db_path):
        decision = _decision(db_path)
        service = OrderService(db_path)
        first = service.execute_decision(decision["id"])
        second = service.execute_decision(decision["id"])
        assert second["status"] == "executed"
        assert [o["id"] for o in second["orders"]] == [first["order"]["id"]]
        assert len(list_orders(db_path)) == 1

    def test_buy_without_ref_price_rejected(self, db_path):
        decision = _decision(db_path, entry_price=None, position_pct=0.10)
        result = OrderService(db_path).execute_decision(decision["id"])
        assert result["status"] == "rejected"
        assert "参考价格" in result["reason"]

    def test_buy_uses_ref_price_provider(self, db_path):
        decision = _decision(db_path, entry_price=None, position_pct=0.10)
        result = OrderService(db_path, ref_price_provider=lambda t, d: 20.0).execute_decision(decision["id"])
        assert result["status"] == "executed"
        assert result["order"]["quantity"] == 5000  # 10 万 / 20 元

    def test_daily_loss_halts_buy(self, db_path):
        account = get_or_create_default_account(db_path)
        _insert_equity(db_path, account["id"], "2026-01-08", 1_000_000)
        _insert_equity(db_path, account["id"], "2026-01-09", 930_000)  # 跌 7%

        decision = _decision(db_path, trade_date="2026-01-09")
        result = OrderService(db_path).execute_decision(decision["id"])
        assert result["status"] == "rejected"
        assert "熔断" in result["reason"]

    def test_sell_without_position_rejected(self, db_path):
        decision = _decision(db_path, rating="Sell", action="Sell", position_pct=None)
        result = OrderService(db_path).execute_decision(decision["id"])
        assert result["status"] == "rejected"
        assert "无可卖持仓" in result["reason"]

    def test_sell_entire_position(self, db_path):
        account = get_or_create_default_account(db_path)
        _filled_order(db_path, account["id"], "600000", "buy", 2000, 10.0, "2026-01-05")

        decision = _decision(db_path, rating="Sell", action="Sell", position_pct=None)
        result = OrderService(db_path).execute_decision(decision["id"])
        assert result["status"] == "executed"
        assert result["order"]["side"] == "sell"
        assert result["order"]["quantity"] == 2000

    def test_underweight_sells_half(self, db_path):
        account = get_or_create_default_account(db_path)
        _filled_order(db_path, account["id"], "600000", "buy", 2000, 10.0, "2026-01-05")

        decision = _decision(db_path, rating="Underweight", action="Underweight", position_pct=None)
        result = OrderService(db_path).execute_decision(decision["id"])
        assert result["order"]["quantity"] == 1000  # 2000 // 2

    def test_blocked_by_judge(self, db_path):
        decision = _decision(db_path)
        service = OrderService(db_path, judge=StubJudge(VERDICT_BLOCK, "止损价异常"))
        result = service.execute_decision(decision["id"])
        assert result["status"] == "blocked"
        assert "止损价异常" in result["reason"]
        assert list_orders(db_path) == []
        # 判断记录已落库
        calls = list_judge_calls(db_path, decision["id"])
        assert len(calls) == 1
        assert calls[0]["verdict"] == VERDICT_BLOCK

    def test_judge_pass_creates_order(self, db_path):
        decision = _decision(db_path)
        service = OrderService(db_path, judge=StubJudge(VERDICT_PASS))
        result = service.execute_decision(decision["id"])
        assert result["status"] == "executed"
        assert list_judge_calls(db_path, decision["id"])[0]["verdict"] == VERDICT_PASS
