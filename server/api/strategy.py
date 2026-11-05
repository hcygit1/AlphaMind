"""Strategy Lab API：策略模板 / 回测执行 / 历史回测。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/strategy", tags=["strategy"])


class StrategyBacktestRequest(BaseModel):
    name: str = Field(min_length=1)
    rules: dict[str, Any]
    start: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


@router.get("/templates")
def list_templates(request: Request) -> list[dict]:
    return request.app.state.strategy_service.list_templates()


@router.post("/backtest")
def run_backtest(request: Request, payload: StrategyBacktestRequest) -> dict:
    try:
        return request.app.state.strategy_service.backtest(
            payload.name, payload.rules, payload.start, payload.end
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs")
def list_runs(request: Request, name: str | None = None) -> list[dict]:
    return request.app.state.strategy_service.list_runs(name)


@router.get("/runs/{run_id}")
def get_run(request: Request, run_id: str) -> dict:
    run = request.app.state.strategy_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"回测记录不存在: {run_id}")
    return run
