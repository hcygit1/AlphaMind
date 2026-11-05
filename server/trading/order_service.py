"""订单服务：决策 → 订单（方向推导、仓位换算、护栏检查、幂等控制）。

持仓不落表，从已成交订单推导；A 股 T+1：买入当日不可卖。
护栏：单票仓位截断、现金与总仓位上限约束、日亏损熔断。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from server.db.trading_repositories import (
    create_order,
    get_decision,
    get_or_create_default_account,
    list_latest_equity_snapshots,
    list_orders,
    list_orders_by_decision,
    record_judge_call,
    update_decision,
)
from server.trading.broker import round_to_lot
from server.trading.extraction import DecisionRecord
from server.trading.judge import VERDICT_BLOCK, Judge
from server.trading.settings import (
    DEFAULT_POSITION_PCT,
    DAILY_LOSS_HALT_PCT,
    MAX_POSITION_PCT,
    MAX_TOTAL_POSITION_PCT,
)

# ref_price_provider(ticker, trade_date) -> 最近收盘价 | None
RefPriceProvider = Callable[[str, str], float | None]

# rating/action → 订单方向；Hold 及未知不下单
_RATING_DIRECTION = {
    "Buy": "buy",
    "Overweight": "buy",
    "Sell": "sell",
    "Underweight": "sell",
}


class OrderError(Exception):
    """决策不存在等不可恢复错误。"""


def resolve_direction(decision: dict[str, Any]) -> str | None:
    """action 优先（Trader 提案），缺失时按 rating 方向推导；Hold/未知 → None。"""
    action = str(decision.get("action") or "").capitalize()
    if action in ("Buy", "Sell"):
        return action.lower()
    if action == "Hold":
        return None
    return _RATING_DIRECTION.get(str(decision.get("rating") or ""))


def next_business_day(date_str: str) -> str:
    """下一个工作日（跳过周末；节假日由后续 pending 扫描顺延处理）。"""
    ts = pd.Timestamp(date_str)
    return str((ts + pd.tseries.offsets.BDay(1)).date())


def get_positions(
    db_path: Path | str, account_id: str, as_of: str | None = None
) -> dict[str, dict[str, Any]]:
    """从已成交订单推导持仓。

    - quantity/avg_cost：含当日买入（成本含费用）
    - available：T+1 可卖数量，``as_of`` 当日买入不计入
    """
    orders = [
        o
        for o in list_orders(db_path, account_id=account_id, status="filled")
        if o.get("side") in ("buy", "sell")
    ]
    orders.sort(key=lambda o: (str(o["exec_date"]), str(o["id"])))

    positions: dict[str, dict[str, Any]] = {}
    for order in orders:
        ticker = order["ticker"]
        pos = positions.setdefault(
            ticker, {"quantity": 0, "available": 0, "cost_total": 0.0, "avg_cost": 0.0}
        )
        qty = int(order["fill_quantity"] or 0)
        if qty <= 0:
            continue
        if order["side"] == "buy":
            pos["quantity"] += qty
            pos["cost_total"] += qty * float(order["fill_price"] or 0) + float(
                order["fee_amount"] or 0
            )
            if as_of is None or str(order["exec_date"]) < as_of:
                pos["available"] += qty
        else:
            pos["quantity"] -= qty
            pos["available"] -= qty
            avg = pos["avg_cost"]
            if avg > 0:
                pos["cost_total"] = max(0.0, pos["cost_total"] - avg * qty)
        if pos["quantity"] > 0:
            pos["avg_cost"] = pos["cost_total"] / pos["quantity"]
        else:
            pos["avg_cost"] = 0.0

    return {t: p for t, p in positions.items() if p["quantity"] > 0}


class OrderService:
    """执行决策生成 pending 订单；撮合（T+1 开盘）由 refresh 流程完成。"""

    def __init__(
        self,
        db_path: Path | str,
        judge: Judge | None = None,
        ref_price_provider: RefPriceProvider | None = None,
    ):
        self.db_path = db_path
        self.judge = judge
        self.ref_price_provider = ref_price_provider

    def execute_decision(
        self, decision_id: str, judge_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """执行决策：Judge 校验 → 方向/数量推导 → 护栏 → 落 pending 订单。

        返回 ``{"status": executed|skipped|blocked|rejected, ...}``；
        幂等：已执行的决策再次调用直接返回已有订单。
        """
        decision = get_decision(self.db_path, decision_id)
        if not decision:
            raise OrderError("决策不存在")

        if decision["status"] == "executed":
            return {
                "status": "executed",
                "orders": list_orders_by_decision(self.db_path, decision_id),
            }

        record = DecisionRecord(
            rating=decision["rating"],
            action=decision["action"],
            entry_price=decision["entry_price"],
            stop_loss=decision["stop_loss"],
            price_target=decision["price_target"],
            position_pct=decision["position_pct"],
            settlement_days=decision["settlement_days"],
        )
        if self.judge is not None:
            result = self.judge.evaluate(record, context=judge_context)
            record_judge_call(
                self.db_path,
                decision_id,
                judge_name=result.judge_name,
                verdict=result.verdict,
                latency_ms=result.latency_ms,
                detail=result.to_detail(),
            )
            update_decision(
                self.db_path, decision_id, judge_json=json.dumps(result.to_detail(), ensure_ascii=False)
            )
            if result.verdict == VERDICT_BLOCK:
                blocked = [c for c in result.checks if c.get("severity") == VERDICT_BLOCK]
                return {"status": "blocked", "reason": "; ".join(
                    c.get("message", "") for c in blocked
                )}

        direction = resolve_direction(decision)
        if direction is None:
            update_decision(self.db_path, decision_id, status="skipped")
            return {"status": "skipped", "reason": "Hold 或方向未知，不下单"}

        account = get_or_create_default_account(self.db_path)
        exec_date = next_business_day(str(decision["trade_date"]))
        positions = get_positions(self.db_path, account["id"], as_of=exec_date)

        if direction == "buy":
            outcome = self._build_buy_order(decision, account, positions, exec_date)
        else:
            outcome = self._build_sell_order(decision, account, positions, exec_date)
        if outcome.get("status") == "rejected":
            return outcome

        order = create_order(
            self.db_path,
            decision_id=decision_id,
            account_id=account["id"],
            ticker=decision["ticker"],
            side=outcome["side"],
            quantity=outcome["quantity"],
            exec_date=exec_date,
        )
        update_decision(self.db_path, decision_id, status="executed")
        return {"status": "executed", "order": order}

    # ---- 买入 ----

    def _build_buy_order(
        self, decision: dict, account: dict, positions: dict, exec_date: str
    ) -> dict[str, Any]:
        ref_price = self._ref_price(decision)
        if not ref_price:
            return {"status": "rejected", "reason": "缺少参考价格（entry_price 与行情均缺失）"}

        daily_loss = self._daily_loss_pct(account["id"])
        if daily_loss is not None and daily_loss > DAILY_LOSS_HALT_PCT:
            return {"status": "rejected", "reason": f"日亏损 {daily_loss:.1%} 超过熔断阈值，暂停买入"}

        equity = float(account["cash"]) + sum(
            p["cost_total"] for p in positions.values()
        )
        pct = decision["position_pct"] or DEFAULT_POSITION_PCT.get(decision["rating"])
        if not pct:
            return {"status": "rejected", "reason": "无法确定目标仓位"}
        pct = min(float(pct), MAX_POSITION_PCT)  # 单票护栏：截断

        pending_buy_amount = self._pending_buy_amount(account["id"], ref_price_hint=None)
        # 总仓位护栏：买入后现金 ≥ (1 - MAX_TOTAL_POSITION_PCT) × 净值
        max_buy_amount = float(account["cash"]) - (1 - MAX_TOTAL_POSITION_PCT) * (
            equity + pending_buy_amount
        )
        target_amount = min(equity * pct, max_buy_amount)
        if target_amount < ref_price:
            return {"status": "rejected", "reason": "可用资金不足"}

        quantity = round_to_lot(int(target_amount // ref_price))
        if quantity <= 0:
            return {"status": "rejected", "reason": "可买金额不足一手"}
        return {"side": "buy", "quantity": quantity}

    def _pending_buy_amount(self, account_id: str, ref_price_hint: float | None) -> float:
        """已挂 pending 买单的预估占用金额（用对应决策的 entry_price 估算）。"""
        total = 0.0
        for order in list_orders(self.db_path, account_id=account_id, status="pending"):
            if order["side"] != "buy":
                continue
            price = (get_decision(self.db_path, order["decision_id"]) or {}).get("entry_price")
            if price:
                total += int(order["quantity"]) * float(price)
            elif ref_price_hint:
                total += int(order["quantity"]) * ref_price_hint
        return total

    def _ref_price(self, decision: dict) -> float | None:
        if decision.get("entry_price"):
            return float(decision["entry_price"])
        if self.ref_price_provider:
            return self.ref_price_provider(decision["ticker"], str(decision["trade_date"]))
        return None

    # ---- 卖出 ----

    def _build_sell_order(
        self, decision: dict, account: dict, positions: dict, exec_date: str
    ) -> dict[str, Any]:
        pos = positions.get(decision["ticker"])
        available = int(pos["available"]) if pos else 0
        if available <= 0:
            return {"status": "rejected", "reason": "无可卖持仓（含 T+1 限制）"}

        if str(decision["rating"]) == "Underweight" and str(decision.get("action") or "") != "Sell":
            quantity = round_to_lot(available // 2)  # 减仓一半
        else:
            quantity = available  # 全部卖出
        if quantity <= 0:
            return {"status": "rejected", "reason": "可卖数量不足一手"}
        return {"side": "sell", "quantity": quantity}

    # ---- 净值 ----

    def _daily_loss_pct(self, account_id: str) -> float | None:
        """最近两条净值快照的日跌幅；无快照返回 None（不拦截）。"""
        snapshots = list_latest_equity_snapshots(self.db_path, account_id, limit=2)
        if len(snapshots) < 2:
            return None
        latest, prev = snapshots[0], snapshots[1]
        prev_equity = float(prev["total_equity"] or 0)
        if prev_equity <= 0:
            return None
        return (prev_equity - float(latest["total_equity"] or 0)) / prev_equity
