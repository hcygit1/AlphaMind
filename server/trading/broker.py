"""模拟撮合引擎：T+1 开盘价成交、涨跌停拒单、A 股手数与费用规则。

纯逻辑模块，不碰数据库；价格数据通过 ``price_provider`` 回调注入，
便于测试与替换数据源（日线缓存 / 实时行情）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from server.trading.settings import (
    COMMISSION_MIN,
    COMMISSION_RATE,
    LOT_SIZE,
    STAMP_TAX_SELL,
)

STATUS_FILLED = "filled"
STATUS_REJECTED = "rejected"
STATUS_PENDING = "pending"  # 执行日行情数据未到，等下次扫描

# price_provider(exec_date, ticker) -> {"open": float, "limit_up": float|None, "limit_down": float|None} | None
PriceProvider = Callable[[str, str], dict | None]


@dataclass
class FillResult:
    status: str
    fill_price: float | None = None
    fill_quantity: int | None = None
    fee_amount: float | None = None
    reject_reason: str | None = None


def compute_fee(side: str, price: float, quantity: int) -> float:
    """A 股费用：佣金万 2.5（最低 5 元），卖出加印花税千 1。"""
    amount = price * quantity
    commission = max(amount * COMMISSION_RATE, COMMISSION_MIN)
    fee = commission
    if side.lower() == "sell":
        fee += amount * STAMP_TAX_SELL
    return round(fee, 2)


def round_to_lot(quantity: int) -> int:
    """向下取整到 A 股手数（100 股）。"""
    return (int(quantity) // LOT_SIZE) * LOT_SIZE


class SimulatedBroker:
    """按 T+1 开盘价模拟撮合。

    - 买入开盘价 >= 涨停价 → 拒单（涨停买不进）；卖出开盘价 <= 跌停价 → 拒单。
    - limit_up/limit_down 为 None 或 0（数据源用 0 表示缺失）时跳过检查。
    - 行情数据未到 → pending，等下次扫描。
    """

    def __init__(self, price_provider: PriceProvider):
        self._price_provider = price_provider

    def try_fill(self, ticker: str, side: str, quantity: int, exec_date: str) -> FillResult:
        quote = self._price_provider(exec_date, ticker)
        if quote is None:
            return FillResult(status=STATUS_PENDING)

        lot_quantity = round_to_lot(quantity)
        if lot_quantity <= 0:
            return FillResult(
                status=STATUS_REJECTED, reject_reason=f"数量不足一手（{LOT_SIZE} 股）"
            )

        open_price = float(quote["open"])
        limit_up = quote.get("limit_up")
        limit_down = quote.get("limit_down")

        side_lower = side.lower()
        if side_lower == "buy" and limit_up and open_price >= float(limit_up):
            return FillResult(status=STATUS_REJECTED, reject_reason="开盘涨停，无法买入")
        if side_lower == "sell" and limit_down and open_price <= float(limit_down):
            return FillResult(status=STATUS_REJECTED, reject_reason="开盘跌停，无法卖出")

        return FillResult(
            status=STATUS_FILLED,
            fill_price=open_price,
            fill_quantity=lot_quantity,
            fee_amount=compute_fee(side, open_price, lot_quantity),
        )
