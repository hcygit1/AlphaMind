import json
from pathlib import Path

from alphamind.agent_runtime.context.types import AgentContext
from alphamind.agent_runtime.tools.deep_research import DeepResearchTool
from alphamind.agent_runtime.tools.report_summary import ReportSummaryTool
from alphamind.agent_runtime.tools.trading import ExecuteDecisionTool, TradingQueryTool
from server.db.connection import init_db
from server.db.repositories import upsert_default_identity, upsert_report
from server.db.trading_repositories import (
    create_decision,
    create_order,
    get_decision,
    get_or_create_default_account,
    update_decision,
    update_order,
)
from server.trading.extraction import DecisionRecord
from server.trading.judge import Judge, JudgeResult, VERDICT_PASS


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


def test_report_summary_tool_reads_active_report_tab(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "market_report": "市场章节原文：需求持续恢复。",
                "final_trade_decision": "**Rating**: Hold\n\n**Executive Summary**: 总摘要。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    init_db(db_path)
    upsert_default_identity(db_path)
    report = upsert_report(db_path, "300750", "2026-06-03", "Hold", "总摘要", str(state_path))

    result = ReportSummaryTool(db_path).run(
        {},
        AgentContext(
            user_id="default_user",
            workspace_id="default_workspace",
            session_id="session_1",
            page={"context": {"active_report_id": report["id"], "active_tab": "market"}},
        ),
    )

    assert result.status == "completed"
    assert "市场分析" in result.content
    assert "需求持续恢复" in result.content
    assert result.payload["active_tab"] == "market"


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


# ---- Trading 工具 ----


class StubJudge(Judge):
    name = "stub"

    def __init__(self, verdict: str = VERDICT_PASS, message: str = "test"):
        self.verdict = verdict
        self.message = message
        self.seen_context = None

    def evaluate(self, decision, context=None) -> JudgeResult:
        self.seen_context = context
        checks = (
            [] if self.verdict == VERDICT_PASS
            else [{"severity": self.verdict, "message": self.message}]
        )
        return JudgeResult(
            judge_name=self.name, verdict=self.verdict, checks=checks,
            latency_ms=1, provider="stub",
        )


def _ctx(report_id: str | None = None) -> AgentContext:
    page = {"context": {"active_report_id": report_id}} if report_id else {}
    return AgentContext(
        user_id="default_user",
        workspace_id="default_workspace",
        session_id="session_1",
        page=page,
    )


def _buy_decision(db_path, tmp_path, action="Buy", rating="Buy"):
    state_path = tmp_path / f"state_{rating}_{action}.json"
    state_path.write_text(
        json.dumps({"final_trade_decision": "**Rating**: " + rating}, ensure_ascii=False),
        encoding="utf-8",
    )
    report = upsert_report(
        db_path, ticker="600000", trade_date="2026-01-05", signal=rating,
        summary="s", state_path=str(state_path),
    )
    return create_decision(
        db_path, report_id=report["id"], ticker="600000", trade_date="2026-01-05",
        record=DecisionRecord(rating=rating, action=action, entry_price=10.0),
    )


def test_trading_query_tool_empty_account(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)

    result = TradingQueryTool(db_path).run({}, _ctx())

    assert result.status == "completed"
    assert result.payload["cash"] == 1_000_000.0
    assert result.payload["positions"] == []
    assert "无持仓" in result.content


def test_trading_query_tool_lists_positions_and_orders(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    decision = _buy_decision(db_path, tmp_path)
    update_decision(db_path, decision["id"], status="executed")
    account = get_or_create_default_account(db_path)
    order = create_order(
        db_path, decision_id=decision["id"], account_id=account["id"],
        ticker="600000", side="buy", quantity=1000, exec_date="2026-01-06",
    )
    update_order(
        db_path, order["id"], status="filled",
        fill_price=10.0, fill_quantity=1000, fee_amount=5.0,
    )

    result = TradingQueryTool(db_path).run({}, _ctx())

    assert result.status == "completed"
    assert result.payload["positions"] == [
        {"ticker": "600000", "quantity": 1000, "available": 1000,
         "cost_total": 10005.0, "avg_cost": 10.005},
    ]
    assert "600000" in result.content
    assert "买入" in result.content


def test_execute_decision_tool_executes_buy_from_report_context(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    decision = _buy_decision(db_path, tmp_path)

    judge = StubJudge()
    tool = ExecuteDecisionTool(db_path, judge=judge)
    result = tool.run({}, _ctx(decision["report_id"]))

    assert result.status == "completed"
    assert "已下单" in result.content
    outcome = result.payload["outcome"]
    assert outcome["status"] == "executed"
    assert outcome["order"]["ticker"] == "600000"
    assert outcome["order"]["side"] == "buy"
    # Judge 拿到了报告页决策上下文
    assert judge.seen_context == {"pm_decision": "**Rating**: Buy"}
    # 决策状态落库为 executed
    assert get_decision(db_path, decision["id"])["status"] == "executed"


def test_execute_decision_tool_skips_hold(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    decision = _buy_decision(db_path, tmp_path, action="Hold", rating="Hold")

    result = ExecuteDecisionTool(db_path, judge=StubJudge()).run({}, _ctx(decision["report_id"]))

    assert result.status == "completed"
    assert result.payload["outcome"]["status"] == "skipped"
    assert "已跳过" in result.content
    assert get_decision(db_path, decision["id"])["status"] == "skipped"


def test_execute_decision_tool_fails_without_report_context(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)

    result = ExecuteDecisionTool(db_path, judge=StubJudge()).run({}, _ctx())

    assert result.status == "failed"
    assert "请先打开一份报告" in result.content


def test_execute_decision_tool_fails_when_report_has_no_decision(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    report = upsert_report(
        db_path, ticker="600000", trade_date="2026-01-05", signal="Hold",
        summary="s", state_path="/tmp/state.json",
    )

    result = ExecuteDecisionTool(db_path, judge=StubJudge()).run({}, _ctx(report["id"]))

    assert result.status == "failed"
    assert "没有对应的交易决策" in result.content
