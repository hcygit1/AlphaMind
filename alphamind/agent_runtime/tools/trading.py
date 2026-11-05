"""Trading tools: 查询账户/持仓/订单，执行当前报告的交易决策。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.tools.base import ToolResult
from server.db.trading_repositories import (
    get_or_create_default_account,
    list_decisions,
    list_orders,
)
from server.trading.order_service import OrderError, OrderService, get_positions


class TradingQueryTool:
    name = "trading_query"

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    def run(self, arguments: dict[str, Any], context: AgentContext) -> ToolResult:
        account = get_or_create_default_account(self.db_path)
        positions = get_positions(self.db_path, account["id"])
        orders = list_orders(self.db_path, account_id=account["id"])
        pending_decisions = [d for d in list_decisions(self.db_path) if d["status"] == "draft"]

        lines = [f"模拟账户「{account['name']}」：现金 {account['cash']:,.2f} 元。"]
        if positions:
            holdings = "、".join(
                f"{ticker} {pos['quantity']} 股（可卖 {pos['available']}）"
                for ticker, pos in positions.items()
            )
            lines.append(f"当前持仓：{holdings}。")
        else:
            lines.append("当前无持仓。")
        recent = orders[-3:]
        if recent:
            order_text = "；".join(
                f"{o['exec_date']} {o['ticker']} {'买入' if o['side'] == 'buy' else '卖出'} "
                f"{o['quantity']} 股（{o['status']}）"
                for o in reversed(recent)
            )
            lines.append(f"最近订单：{order_text}。")
        if pending_decisions:
            lines.append(f"有 {len(pending_decisions)} 条待执行决策，可到报告页或 Paper Trading 页执行。")

        return ToolResult(
            tool_name=self.name,
            status="completed",
            content="\n".join(lines),
            payload={
                "account_id": account["id"],
                "cash": account["cash"],
                "positions": [
                    {"ticker": ticker, **pos} for ticker, pos in positions.items()
                ],
                "pending_decisions": len(pending_decisions),
            },
        )


class ExecuteDecisionTool:
    name = "execute_decision"

    def __init__(self, db_path: Path | str, judge: Any | None = None):
        self.db_path = Path(db_path)
        self.judge = judge

    def run(self, arguments: dict[str, Any], context: AgentContext) -> ToolResult:
        decision_id = arguments.get("decision_id")
        if not decision_id:
            page_context = context.page.get("context") or context.page.get("context_json") or {}
            report_id = arguments.get("report_id") or page_context.get("active_report_id")
            if not report_id:
                return ToolResult(
                    tool_name=self.name,
                    status="failed",
                    content="请先打开一份报告，或告诉我决策编号。",
                )
            decision = next(
                (d for d in list_decisions(self.db_path) if d["report_id"] == report_id),
                None,
            )
            if not decision:
                return ToolResult(
                    tool_name=self.name,
                    status="failed",
                    content="这份报告没有对应的交易决策。",
                    payload={"report_id": report_id},
                )
            decision_id = decision["id"]

        service = OrderService(self.db_path, judge=self.judge or _default_judge())
        try:
            outcome = service.execute_decision(str(decision_id), judge_context=_judge_context(self.db_path, str(decision_id)))
        except OrderError as exc:
            return ToolResult(
                tool_name=self.name,
                status="failed",
                content=str(exc),
                payload={"decision_id": decision_id},
            )

        return ToolResult(
            tool_name=self.name,
            status="completed",
            content=_describe(outcome),
            payload={"decision_id": decision_id, "outcome": outcome},
        )


def _default_judge():
    from server.api.trading import build_default_judge

    return build_default_judge()


def _judge_context(db_path: Path, decision_id: str) -> dict[str, Any] | None:
    from server.db.trading_repositories import get_decision
    from server.services.report_service import build_report_detail

    decision = get_decision(db_path, decision_id)
    if not decision:
        return None
    try:
        detail = build_report_detail(db_path, decision["report_id"])
        state = detail.get("state") or {}
        if isinstance(state, dict) and state.get("final_trade_decision"):
            return {"pm_decision": str(state["final_trade_decision"])}
    except Exception:
        pass
    return None


def _describe(outcome: dict[str, Any]) -> str:
    status = outcome.get("status")
    if status == "executed":
        order = outcome.get("order") or (outcome.get("orders") or [{}])[-1]
        if order:
            return (
                f"已下单：{order['ticker']} {'买入' if order['side'] == 'buy' else '卖出'} "
                f"{order['quantity']} 股，执行日 {order['exec_date']}（T+1 开盘撮合）。"
            )
        return "决策已执行。"
    if status == "skipped":
        return f"已跳过：{outcome.get('reason', '无需下单')}"
    if status == "blocked":
        return f"Judge 拦截：{outcome.get('reason', '决策未通过风控校验')}"
    return f"未成交：{outcome.get('reason', '订单被拒绝')}"
