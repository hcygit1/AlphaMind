"""自动化调度器：守护线程，每天到点后对自选股逐个跑深度投研。

- 每 interval 秒检查一次：enabled 且 now ≥ run_time 且今天没跑过 → 触发
- watchlist 为空不触发、不标记（用户当天加股票后仍可自动跑）
- 自选股串行执行（DB 限制：同时只能有一个活跃投研任务）
- 单个 ticker 失败不影响后续；全部尝试完标记 last_run_date
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from server.db.repositories import (
    get_automation_settings,
    list_watchlist,
    update_automation_settings,
)
from server.services.research_service import ResearchService

logger = logging.getLogger(__name__)

DEFAULT_CHECK_INTERVAL_SECONDS = 30.0


class SchedulerService:
    def __init__(
        self,
        db_path: Path | str,
        research_service: ResearchService,
        interval_seconds: float = DEFAULT_CHECK_INTERVAL_SECONDS,
    ) -> None:
        self.db_path = Path(db_path)
        self.research_service = research_service
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="alphamind-scheduler"
        )
        self._thread.start()
        logger.info("自动化调度器已启动（每 %.0f 秒检查一次）", self.interval_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            try:
                self.tick(datetime.now())
            except Exception:
                logger.exception("调度器 tick 异常")

    def tick(self, now: datetime) -> bool:
        """检查是否满足触发条件并执行；返回是否触发了本轮。可独立单测。"""
        settings = get_automation_settings(self.db_path)
        if not settings["enabled"]:
            return False
        today = now.strftime("%Y-%m-%d")
        if settings["last_run_date"] == today:
            return False
        if now.strftime("%H:%M") < settings["run_time"]:
            return False

        tickers = list_watchlist(self.db_path, enabled_only=True)
        if not tickers:
            return False

        logger.info(
            "自动化调度触发：%s 待跑 %d 只", today, len(tickers)
        )
        for item in tickers:
            if self._stop_event.is_set():
                break
            self._run_one(item["ticker"], today)
        update_automation_settings(self.db_path, last_run_date=today)
        return True

    def _run_one(self, ticker: str, trade_date: str) -> None:
        try:
            task = self.research_service.create_task(ticker, trade_date)
        except RuntimeError as exc:
            # 已有活跃任务（手动启动等）：跳过该 ticker，本轮稍后可重试
            logger.warning("自动化调度：%s 跳过（%s）", ticker, exc)
            return
        logger.info("自动化调度：开始投研 %s（task %s）", ticker, task["id"])
        thread = self.research_service.start_task(task["id"])
        if thread is not None:
            thread.join()  # 串行：DB 限制同时只能有一个活跃任务
        final = self.research_service.get_task(task["id"])
        status = final.get("status") if final else "unknown"
        logger.info("自动化调度：%s 完成（%s）", ticker, status)
