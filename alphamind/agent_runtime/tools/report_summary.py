"""Report summary tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.tools.base import ToolResult
from server.db.repositories import get_report


class ReportSummaryTool:
    name = "report_summary"

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    def run(self, arguments: dict[str, Any], context: AgentContext) -> ToolResult:
        page_context = context.page.get("context") or context.page.get("context_json") or {}
        report_id = arguments.get("report_id") or page_context.get("active_report_id")
        if not report_id:
            return ToolResult(
                tool_name=self.name,
                status="failed",
                content="当前页面没有可总结的报告。请先打开一个报告。",
            )

        report = get_report(self.db_path, str(report_id))
        if not report:
            return ToolResult(
                tool_name=self.name,
                status="failed",
                content="没有找到对应报告。",
                payload={"report_id": report_id},
            )

        content = (
            f"{report['ticker']} 在 {report['trade_date']} 的最终信号是 "
            f"{report['signal']}。摘要：{report['summary']}"
        )
        return ToolResult(
            tool_name=self.name,
            status="completed",
            content=content,
            payload={"report_id": report_id},
        )
