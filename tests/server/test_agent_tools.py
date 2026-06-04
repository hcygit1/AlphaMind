from pathlib import Path

from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.tools.deep_research import DeepResearchTool
from alphamind.agent_runtime.tools.report_summary import ReportSummaryTool
from server.db.connection import init_db
from server.db.repositories import upsert_default_identity, upsert_report


class FakeResearchService:
    def __init__(self):
        self.started_tasks: list[str] = []

    def create_task(self, ticker: str, trade_date: str):
        return {
            "id": "task_1",
            "ticker": ticker,
            "trade_date": trade_date,
            "status": "pending",
        }

    def start_task(self, task_id: str):
        self.started_tasks.append(task_id)
        return None


def test_report_summary_tool_reads_current_report(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    state_path = tmp_path / "state.json"
    state_path.write_text('{"final_trade_decision":"**Rating**: Hold"}', encoding="utf-8")
    init_db(db_path)
    upsert_default_identity(db_path)
    report = upsert_report(db_path, "300750", "2026-06-03", "Hold", "摘要", str(state_path))

    tool = ReportSummaryTool(db_path)
    result = tool.run(
        {},
        AgentContext(
            user_id="default_user",
            workspace_id="default_workspace",
            session_id="session_1",
            page={"context": {"active_report_id": report["id"]}},
        ),
    )

    assert result.status == "completed"
    assert "摘要" in result.content
    assert result.payload["report_id"] == report["id"]


def test_report_summary_tool_fails_without_report_id(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)

    result = ReportSummaryTool(db_path).run(
        {},
        AgentContext("default_user", "default_workspace", "session_1"),
    )

    assert result.status == "failed"
    assert "报告" in result.content


def test_deep_research_tool_creates_task_from_arguments():
    service = FakeResearchService()
    tool = DeepResearchTool(service)
    result = tool.run(
        {"ticker": "300750", "trade_date": "2026-06-03"},
        AgentContext("default_user", "default_workspace", "session_1"),
    )

    assert result.status == "accepted"
    assert result.payload["task_id"] == "task_1"
    assert service.started_tasks == ["task_1"]


def test_deep_research_tool_fails_without_ticker_or_trade_date():
    result = DeepResearchTool(FakeResearchService()).run(
        {},
        AgentContext("default_user", "default_workspace", "session_1"),
    )

    assert result.status == "failed"
    assert "股票代码" in result.content
