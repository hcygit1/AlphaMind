"""Deep research task orchestration and SSE event buffering."""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from server.core.llm_config import build_research_config
from server.db.repositories import (
    create_research_task_if_none_active,
    get_research_task,
    list_active_research_tasks,
    update_research_task,
    upsert_report,
)
from server.db.trading_repositories import create_decision
from server.services.report_service import extract_summary
from server.trading.extraction import load_state, parse_decision_from_state

logger = logging.getLogger(__name__)


ResearchRunner = Callable[[str, str, Callable[..., None]], dict[str, Any]]
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
# SSE 事件缓冲上限：超过后裁剪最旧事件，防止长期运行内存无界
MAX_EVENTS_PER_TASK = 500


def default_runner(ticker: str, trade_date: str, emit: Callable[..., None]) -> dict[str, Any]:
    from alphamind.graph.trading_graph import AlphaMindGraph
    from server.services.token_usage import TokenUsageCallback

    config = build_research_config()
    tracker = TokenUsageCallback()
    graph = AlphaMindGraph(debug=False, config=config, callbacks=[tracker])
    final_state, signal = graph.propagate(ticker, trade_date)
    state_path = (
        Path(config["results_dir"])
        / graph.ticker
        / "AlphaMindStrategy_logs"
        / f"full_states_log_{trade_date}.json"
    )
    emit(stage="pm", message="最终决策完成")
    return {
        "state_path": str(state_path),
        "signal": signal,
        "summary": extract_summary(final_state),
        "token_usage": tracker.snapshot(),
    }


class ResearchService:
    def __init__(self, db_path: Path | str, runner: ResearchRunner = default_runner):
        self.db_path = Path(db_path)
        self.runner = runner
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._lock = threading.Lock()

    def create_task(self, ticker: str, trade_date: str) -> dict[str, Any]:
        task = create_research_task_if_none_active(
            self.db_path,
            ticker=ticker,
            trade_date=trade_date,
        )
        self._emit(task["id"], status="pending", stage=None, message="任务已创建")
        return task

    def start_task(self, task_id: str) -> threading.Thread:
        thread = threading.Thread(target=self.run_task_sync, args=(task_id,), daemon=True)
        thread.start()
        return thread

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        task = get_research_task(self.db_path, task_id)
        if not task:
            return {}
        if task.get("status") in TERMINAL_STATUSES:
            return task

        cancelled = update_research_task(
            self.db_path,
            task_id,
            status="cancelled",
            error_message="任务已中断",
        )
        self._emit(
            task_id,
            status="cancelled",
            stage=cancelled.get("progress_stage"),
            message="任务已中断",
        )
        return cancelled

    def run_task_sync(self, task_id: str) -> None:
        task = get_research_task(self.db_path, task_id)
        if not task:
            raise ValueError(f"Unknown task_id: {task_id}")
        if task.get("status") == "cancelled":
            self._emit(
                task_id,
                status="cancelled",
                stage=task.get("progress_stage"),
                message="任务已中断",
            )
            return
        update_research_task(self.db_path, task_id, status="running")
        self._emit(task_id, status="running", stage=None, message="任务开始运行")

        def emit(stage: str, message: str, payload: dict[str, Any] | None = None) -> None:
            update_research_task(self.db_path, task_id, progress_stage=stage)
            self._emit(
                task_id,
                status="running",
                stage=stage,
                message=message,
                payload=payload or {},
            )

        try:
            result = self.runner(task["ticker"], task["trade_date"], emit)
            current = get_research_task(self.db_path, task_id)
            if current.get("status") == "cancelled":
                self._emit(
                    task_id,
                    status="cancelled",
                    stage=current.get("progress_stage"),
                    message="任务已中断",
                )
                return
            report = upsert_report(
                self.db_path,
                ticker=task["ticker"],
                trade_date=task["trade_date"],
                signal=str(result["signal"]),
                summary=str(result["summary"]),
                state_path=str(result["state_path"]),
            )
            usage = result.get("token_usage") or {}
            update_research_task(
                self.db_path,
                task_id,
                status="completed",
                report_id=report["id"],
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                total_tokens=int(usage.get("total_tokens") or 0),
            )
            self._persist_decision(report["id"], task["ticker"], task["trade_date"], result)
            self._emit(
                task_id,
                status="completed",
                stage="completed",
                message="深度投研完成",
                payload={"report_id": report["id"]},
            )
        except Exception as exc:
            current = get_research_task(self.db_path, task_id)
            if current.get("status") == "cancelled":
                self._emit(
                    task_id,
                    status="cancelled",
                    stage=current.get("progress_stage"),
                    message="任务已中断",
                )
                return
            update_research_task(
                self.db_path,
                task_id,
                status="failed",
                error_message=str(exc),
                failed_stage=current.get("progress_stage"),
            )
            self._emit(
                task_id,
                status="failed",
                stage=current.get("progress_stage"),
                message=str(exc),
            )

    def _persist_decision(
        self,
        report_id: str,
        ticker: str,
        trade_date: str,
        result: dict[str, Any],
    ) -> None:
        """从 state JSON 提取决策并入库；失败只记日志，不影响报告流程。"""
        try:
            state = load_state(str(result["state_path"]))
            record = parse_decision_from_state(state, fallback_rating=str(result["signal"]))
            decision = create_decision(
                self.db_path,
                report_id=report_id,
                ticker=ticker,
                trade_date=trade_date,
                record=record,
            )
            logger.info("决策已入库: %s (%s %s)", decision["id"], ticker, decision["rating"])
        except Exception as exc:
            logger.warning("决策入库失败（不影响报告完成）: %s", exc)

    def get_task(self, task_id: str) -> dict[str, Any]:
        return get_research_task(self.db_path, task_id)

    def get_active_task(self) -> dict[str, Any] | None:
        active_tasks = list_active_research_tasks(self.db_path)
        return active_tasks[0] if active_tasks else None

    def get_events(self, task_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events.get(task_id, []))

    def _emit(
        self,
        task_id: str,
        status: str,
        stage: str | None,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "event": "research_progress",
            "task_id": task_id,
            "status": status,
            "stage": stage,
            "message": message,
            "payload": payload or {},
        }
        with self._lock:
            self._events[task_id].append(event)
            # 仅终态任务裁剪旧事件（保留最新 200 条供 SSE 补发）：
            # 运行中任务的 SSE 客户端按事件序号补发，裁剪会使其错位
            if status in TERMINAL_STATUSES and len(self._events[task_id]) > MAX_EVENTS_PER_TASK:
                del self._events[task_id][:-200]
