from pathlib import Path
from types import SimpleNamespace

import pytest

from server.db.connection import init_db
from server.db.repositories import create_research_task, get_research_task, upsert_default_identity
import server.services.research_service as research_service_module
from server.services.research_service import ResearchService


class FakeRunner:
    def __call__(self, ticker: str, trade_date: str, emit):
        emit(stage="market", message="市场分析完成")
        return {
            "state_path": "/tmp/full_states_log_2026-06-03.json",
            "signal": "Hold",
            "summary": "测试摘要",
        }


def test_research_service_creates_and_runs_task(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)

    service = ResearchService(db_path=db_path, runner=FakeRunner())
    task = service.create_task("300750", "2026-06-03")

    service.run_task_sync(task["id"])

    updated = get_research_task(db_path, task["id"])
    assert updated["status"] == "completed"
    assert updated["progress_stage"] == "market"
    assert updated["report_id"]

    events = service.get_events(task["id"])
    assert events[0]["event"] == "research_progress"
    assert events[-1]["status"] == "completed"
    assert events[-1]["payload"]["report_id"] == updated["report_id"]


def test_research_service_blocks_when_repository_has_active_task(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    create_research_task(db_path, ticker="600519", trade_date="2026-06-03")

    service = ResearchService(db_path=db_path, runner=FakeRunner())

    with pytest.raises(RuntimeError, match="同时只能运行一个"):
        service.create_task("300750", "2026-06-03")


def test_research_service_create_task_uses_atomic_repository_gate(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    calls = []

    def fake_create_if_none_active(db_path_arg, ticker: str, trade_date: str):
        calls.append((Path(db_path_arg), ticker, trade_date))
        return {"id": "task_atomic", "ticker": ticker, "trade_date": trade_date, "status": "pending"}

    monkeypatch.setattr(
        research_service_module,
        "create_research_task_if_none_active",
        fake_create_if_none_active,
    )
    service = ResearchService(db_path=db_path, runner=FakeRunner())

    task = service.create_task("300750", "2026-06-03")

    assert task["id"] == "task_atomic"
    assert calls == [(db_path, "300750", "2026-06-03")]


def test_default_runner_summary_uses_report_summary_extractor(tmp_path: Path, monkeypatch):
    final_state = {
        "final_trade_decision": (
            "**Rating**: Hold\n\n"
            "**Executive Summary**: 复用报告摘要。\n\n"
            "后续正文不应成为索引摘要。"
        )
    }

    class FakeGraph:
        ticker = "300750"

        def __init__(self, debug: bool, config: dict):
            self.config = config

        def propagate(self, ticker: str, trade_date: str):
            return final_state, "Hold"

    monkeypatch.setitem(
        __import__("sys").modules,
        "alphamind.graph.trading_graph",
        SimpleNamespace(AlphaMindGraph=FakeGraph),
    )
    monkeypatch.setitem(research_service_module.DEFAULT_CONFIG, "results_dir", str(tmp_path))

    result = research_service_module.default_runner("300750", "2026-06-03", lambda **kwargs: None)

    assert result["summary"] == "复用报告摘要。"
