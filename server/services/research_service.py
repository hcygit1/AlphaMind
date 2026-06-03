"""Deep research task orchestration and SSE event buffering."""

from __future__ import annotations

import threading
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from alphamind.default_config import DEFAULT_CONFIG
from server.db.repositories import (
    create_research_task,
    get_research_task,
    list_active_research_tasks,
    update_research_task,
    upsert_report,
)


ResearchRunner = Callable[[str, str, Callable[..., None]], dict[str, Any]]


def default_runner(ticker: str, trade_date: str, emit: Callable[..., None]) -> dict[str, Any]:
    from alphamind.graph.trading_graph import AlphaMindGraph

    graph = AlphaMindGraph(debug=False, config=DEFAULT_CONFIG.copy())
    final_state, signal = graph.propagate(ticker, trade_date)
    state_path = (
        Path(DEFAULT_CONFIG["results_dir"])
        / graph.ticker
        / "AlphaMindStrategy_logs"
        / f"full_states_log_{trade_date}.json"
    )
    emit(stage="pm", message="最终决策完成")
    return {
        "state_path": str(state_path),
        "signal": signal,
        "summary": str(final_state.get("final_trade_decision", ""))[:180],
    }


class ResearchService:
    def __init__(self, db_path: Path | str, runner: ResearchRunner = default_runner):
        self.db_path = Path(db_path)
        self.runner = runner
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._lock = threading.Lock()

    def create_task(self, ticker: str, trade_date: str) -> dict[str, Any]:
        running = [
            task for task in self._active_tasks() if task.get("status") in {"pending", "running"}
        ]
        if running:
            raise RuntimeError("同一默认用户同时只能运行一个深度投研任务")
        task = create_research_task(self.db_path, ticker=ticker, trade_date=trade_date)
        self._emit(task["id"], status="pending", stage=None, message="任务已创建")
        return task

    def start_task(self, task_id: str) -> threading.Thread:
        thread = threading.Thread(target=self.run_task_sync, args=(task_id,), daemon=True)
        thread.start()
        return thread

    def run_task_sync(self, task_id: str) -> None:
        task = get_research_task(self.db_path, task_id)
        if not task:
            raise ValueError(f"Unknown task_id: {task_id}")
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
            report = upsert_report(
                self.db_path,
                ticker=task["ticker"],
                trade_date=task["trade_date"],
                signal=str(result["signal"]),
                summary=str(result["summary"]),
                state_path=str(result["state_path"]),
            )
            update_research_task(
                self.db_path,
                task_id,
                status="completed",
                report_id=report["id"],
            )
            self._emit(
                task_id,
                status="completed",
                stage="completed",
                message="深度投研完成",
                payload={"report_id": report["id"]},
            )
        except Exception as exc:
            current = get_research_task(self.db_path, task_id)
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

    def get_task(self, task_id: str) -> dict[str, Any]:
        return get_research_task(self.db_path, task_id)

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

    def _active_tasks(self) -> list[dict[str, Any]]:
        return list_active_research_tasks(self.db_path)
