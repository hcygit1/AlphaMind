"""SimulatedBroker 撮合规则测试：费用、手数、T+1 开盘成交、涨跌停拒单。"""

from __future__ import annotations

from server.trading.broker import (
    STATUS_FILLED,
    STATUS_PENDING,
    STATUS_REJECTED,
    SimulatedBroker,
    compute_fee,
    round_to_lot,
)


def _make_broker(quotes: dict | None = None):
    """quotes: {(date, ticker): quote or None}；缺省返回默认行情。"""
    default = {"open": 10.0, "limit_up": 11.0, "limit_down": 9.0}

    def provider(exec_date: str, ticker: str):
        if quotes is None:
            return default
        return quotes.get((exec_date, ticker))

    return SimulatedBroker(provider)


class TestComputeFee:
    def test_buy_commission_above_min(self):
        # 10 元 × 1000 股 = 10000 元 × 万2.5 = 2.5 → 佣金最低 5 元
        assert compute_fee("buy", 10.0, 1000) == 5.0

    def test_buy_commission_scales(self):
        # 10 元 × 10000 股 = 100000 × 万2.5 = 25 元
        assert compute_fee("buy", 10.0, 10000) == 25.0

    def test_sell_adds_stamp_tax(self):
        # 佣金 25 + 印花税 100000 × 千1 = 100 → 125
        assert compute_fee("sell", 10.0, 10000) == 125.0

    def test_fee_rounded_to_cents(self):
        fee = compute_fee("buy", 3.33, 300)  # 999 × 0.00025 = 0.25 → 最低 5
        assert fee == 5.0


class TestRoundToLot:
    def test_rounds_down_to_100(self):
        assert round_to_lot(250) == 200

    def test_exact_lot_unchanged(self):
        assert round_to_lot(500) == 500

    def test_below_lot_is_zero(self):
        assert round_to_lot(99) == 0


class TestTryFill:
    def test_fills_at_open_price(self):
        result = _make_broker().try_fill("600000", "buy", 1000, "2026-01-06")
        assert result.status == STATUS_FILLED
        assert result.fill_price == 10.0
        assert result.fill_quantity == 1000
        assert result.fee_amount == 5.0

    def test_quantity_rounded_to_lot(self):
        result = _make_broker().try_fill("600000", "buy", 1234, "2026-01-06")
        assert result.status == STATUS_FILLED
        assert result.fill_quantity == 1200

    def test_rejects_buy_at_limit_up(self):
        broker = _make_broker({("2026-01-06", "600000"): {"open": 11.0, "limit_up": 11.0, "limit_down": 9.0}})
        result = broker.try_fill("600000", "buy", 1000, "2026-01-06")
        assert result.status == STATUS_REJECTED
        assert "涨停" in result.reject_reason

    def test_rejects_sell_at_limit_down(self):
        broker = _make_broker({("2026-01-06", "600000"): {"open": 9.0, "limit_up": 11.0, "limit_down": 9.0}})
        result = broker.try_fill("600000", "sell", 1000, "2026-01-06")
        assert result.status == STATUS_REJECTED
        assert "跌停" in result.reject_reason

    def test_buy_at_limit_down_allowed(self):
        broker = _make_broker({("2026-01-06", "600000"): {"open": 9.0, "limit_up": 11.0, "limit_down": 9.0}})
        result = broker.try_fill("600000", "buy", 1000, "2026-01-06")
        assert result.status == STATUS_FILLED

    def test_skips_limit_check_when_missing(self):
        # 数据源用 0 / None 表示涨跌停缺失
        broker = _make_broker({("2026-01-06", "600000"): {"open": 11.0, "limit_up": 0, "limit_down": 0}})
        result = broker.try_fill("600000", "buy", 1000, "2026-01-06")
        assert result.status == STATUS_FILLED

    def test_skips_limit_check_when_none(self):
        broker = _make_broker({("2026-01-06", "600000"): {"open": 10.0, "limit_up": None, "limit_down": None}})
        result = broker.try_fill("600000", "sell", 1000, "2026-01-06")
        assert result.status == STATUS_FILLED

    def test_pending_when_no_data(self):
        broker = _make_broker({})  # 无行情
        result = broker.try_fill("600000", "buy", 1000, "2026-01-06")
        assert result.status == STATUS_PENDING
        assert result.fill_price is None

    def test_rejects_quantity_below_lot(self):
        result = _make_broker().try_fill("600000", "buy", 50, "2026-01-06")
        assert result.status == STATUS_REJECTED
        assert "一手" in result.reject_reason

    def test_uses_exec_date_and_ticker_to_lookup(self):
        broker = _make_broker(
            {
                ("2026-01-06", "600000"): {"open": 10.0},
                ("2026-01-07", "600000"): {"open": 12.0},
                ("2026-01-06", "000001"): {"open": 20.0},
            }
        )
        assert broker.try_fill("600000", "buy", 100, "2026-01-07").fill_price == 12.0
        assert broker.try_fill("000001", "buy", 100, "2026-01-06").fill_price == 20.0
