"""Deep research task creation tool."""

from __future__ import annotations

from typing import Any

from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.tools.base import ToolResult


class DeepResearchTool:
    name = "deep_research"

    def __init__(self, research_service):
        self.research_service = research_service

    def run(self, arguments: dict[str, Any], context: AgentContext) -> ToolResult:
        page_context = context.page.get("context") or context.page.get("context_json") or {}
        ticker = arguments.get("ticker") or page_context.get("ticker")
        trade_date = arguments.get("trade_date") or page_context.get("trade_date")
        if not ticker or not trade_date:
            return ToolResult(
                tool_name=self.name,
                status="failed",
                content="请提供股票代码和分析日期。",
            )

        task = self.research_service.create_task(str(ticker), str(trade_date))
        self.research_service.start_task(task["id"])
        return ToolResult(
            tool_name=self.name,
            status="accepted",
            content=f"已创建 {ticker} 在 {trade_date} 的深度投研任务。",
            payload={
                "task_id": task["id"],
                "ticker": ticker,
                "trade_date": trade_date,
            },
        )
