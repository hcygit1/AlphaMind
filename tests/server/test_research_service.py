from pathlib import Path

import pytest

from server.db.connection import init_db
from server.db.repositories import create_research_task, get_research_task, upsert_default_identity
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
