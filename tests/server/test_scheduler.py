"""自动化调度器测试：触发条件判定、串行执行、last_run_date 标记。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Thread

import pytest

from server.db.connection import init_db
from server.db.repositories import (
    add_watchlist_ticker,
    get_automation_settings,
    update_automation_settings,
    upsert_default_identity,
)
from server.services.scheduler_service import SchedulerService


class FakeResearchService:
    """记录 create_task 调用；start_task 返回立即结束的线程。"""

    def __init__(self, fail_tickers: set[str] | None = None):
        self.calls: list[str] = []
        self.fail_tickers = fail_tickers or set()

    def create_task(self, ticker: str, trade_date: str) -> dict:
        if ticker in self.fail_tickers:
            raise RuntimeError("同一默认用户同时只能运行一个深度投研任务")
        self.calls.append(ticker)
        return {"id": f"task-{ticker}", "ticker": ticker, "trade_date": trade_date, "status": "pending"}

    def start_task(self, task_id: str) -> Thread:
        thread = Thread(target=lambda: None)
        thread.start()
        return thread

    def get_task(self, task_id: str) -> dict:
        return {"id": task_id, "status": "completed"}


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.sqlite3"
    init_db(path)
    upsert_default_identity(path)
    return path


def test_disabled_never_triggers(db_path):
    add_watchlist_ticker(db_path, "600519")
    service = FakeResearchService()
    scheduler = SchedulerService(db_path, service)

    assert scheduler.tick(datetime(2026, 1, 5, 17, 0)) is False
    assert service.calls == []


def test_before_run_time_not_triggered(db_path):
    add_watchlist_ticker(db_path, "600519")
    update_automation_settings(db_path, enabled=True, run_time="16:30")
    service = FakeResearchService()
    scheduler = SchedulerService(db_path, service)

    assert scheduler.tick(datetime(2026, 1, 5, 16, 29)) is False
    assert service.calls == []


def test_already_ran_today_not_triggered(db_path):
    add_watchlist_ticker(db_path, "600519")
    update_automation_settings(db_path, enabled=True, run_time="16:30", last_run_date="2026-01-05")
    service = FakeResearchService()
    scheduler = SchedulerService(db_path, service)

    assert scheduler.tick(datetime(2026, 1, 5, 17, 0)) is False
    assert service.calls == []


def test_empty_watchlist_not_triggered_and_not_marked(db_path):
    update_automation_settings(db_path, enabled=True, run_time="16:30")
    service = FakeResearchService()
    scheduler = SchedulerService(db_path, service)

    assert scheduler.tick(datetime(2026, 1, 5, 17, 0)) is False
    assert service.calls == []
    assert get_automation_settings(db_path)["last_run_date"] is None


def test_triggers_and_runs_watchlist_serially(db_path):
    add_watchlist_ticker(db_path, "600519")
    add_watchlist_ticker(db_path, "300750")
    update_automation_settings(db_path, enabled=True, run_time="16:30")
    service = FakeResearchService()
    scheduler = SchedulerService(db_path, service)

    assert scheduler.tick(datetime(2026, 1, 5, 17, 0)) is True
    assert service.calls == ["600519", "300750"]
    assert get_automation_settings(db_path)["last_run_date"] == "2026-01-05"

    # 当天再 tick 不重复
    assert scheduler.tick(datetime(2026, 1, 5, 18, 0)) is False
    assert service.calls == ["600519", "300750"]


def test_busy_ticker_skipped_others_still_run(db_path):
    add_watchlist_ticker(db_path, "600519")
    add_watchlist_ticker(db_path, "300750")
    update_automation_settings(db_path, enabled=True, run_time="16:30")
    service = FakeResearchService(fail_tickers={"600519"})
    scheduler = SchedulerService(db_path, service)

    assert scheduler.tick(datetime(2026, 1, 5, 17, 0)) is True
    assert service.calls == ["300750"]  # 600519 被跳过，其余继续
    assert get_automation_settings(db_path)["last_run_date"] == "2026-01-05"


def test_boundary_time_equal_triggers(db_path):
    add_watchlist_ticker(db_path, "600519")
    update_automation_settings(db_path, enabled=True, run_time="16:30")
    service = FakeResearchService()
    scheduler = SchedulerService(db_path, service)

    assert scheduler.tick(datetime(2026, 1, 5, 16, 30)) is True
