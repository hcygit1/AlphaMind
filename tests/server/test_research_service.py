from pathlib import Path
from types import SimpleNamespace

import pytest

from server.db.connection import init_db
from server.db.repositories import create_research_task, get_research_task, upsert_default_identity
import server.db.repositories as repositories
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


def test_research_service_cancel_task_marks_task_cancelled(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    service = ResearchService(db_path=db_path, runner=FakeRunner())
    task = service.create_task("300750", "2026-06-03")

    cancelled = service.cancel_task(task["id"])

    assert cancelled["status"] == "cancelled"
    assert cancelled["error_message"] == "任务已中断"
    events = service.get_events(task["id"])
    assert events[-1]["status"] == "cancelled"
    assert events[-1]["message"] == "任务已中断"


def test_research_service_skips_completion_when_task_was_cancelled_before_run(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    called = []

    def runner(ticker: str, trade_date: str, emit):
        called.append((ticker, trade_date))
        return {
            "state_path": "/tmp/full_states_log_2026-06-03.json",
            "signal": "Hold",
            "summary": "测试摘要",
        }

    service = ResearchService(db_path=db_path, runner=runner)
    task = service.create_task("300750", "2026-06-03")
    service.cancel_task(task["id"])

    service.run_task_sync(task["id"])

    updated = get_research_task(db_path, task["id"])
    assert updated["status"] == "cancelled"
    assert updated["report_id"] is None
    assert called == []


def test_research_service_does_not_overwrite_cancelled_task_after_runner_returns(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)

    def runner(ticker: str, trade_date: str, emit):
        task = repositories.get_research_task(db_path, task_id)
        repositories.update_research_task(db_path, task["id"], status="cancelled", error_message="任务已中断")
        return {
            "state_path": "/tmp/full_states_log_2026-06-03.json",
            "signal": "Hold",
            "summary": "测试摘要",
        }

    service = ResearchService(db_path=db_path, runner=runner)
    task = service.create_task("300750", "2026-06-03")
    task_id = task["id"]

    service.run_task_sync(task_id)

    updated = get_research_task(db_path, task_id)
    assert updated["status"] == "cancelled"
    assert updated["report_id"] is None


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
    monkeypatch.setattr(
        research_service_module,
        "build_research_config",
        lambda: {"results_dir": str(tmp_path)},
    )

    result = research_service_module.default_runner("300750", "2026-06-03", lambda **kwargs: None)

    assert result["summary"] == "复用报告摘要。"
