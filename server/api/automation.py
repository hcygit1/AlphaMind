"""自动化调度 API：自选股管理 + 定时投研设置。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from server.db.repositories import (
    add_watchlist_ticker,
    get_automation_settings,
    list_watchlist,
    remove_watchlist_ticker,
    update_automation_settings,
)
from server.models.schemas import AutomationSettingsUpdate

router = APIRouter(prefix="/api/automation", tags=["automation"])


@router.get("/watchlist")
def get_watchlist(request: Request) -> list[dict]:
    return list_watchlist(request.app.state.database_path)


@router.post("/watchlist/{ticker}")
def add_ticker(ticker: str, request: Request) -> dict:
    ticker = ticker.strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker cannot be empty")
    return add_watchlist_ticker(request.app.state.database_path, ticker)


@router.delete("/watchlist/{ticker}")
def delete_ticker(ticker: str, request: Request) -> dict:
    if not remove_watchlist_ticker(request.app.state.database_path, ticker):
        raise HTTPException(status_code=404, detail="Ticker not in watchlist")
    return {"removed": ticker}


@router.get("/settings")
def read_settings(request: Request) -> dict:
    return get_automation_settings(request.app.state.database_path)


@router.put("/settings")
def write_settings(payload: AutomationSettingsUpdate, request: Request) -> dict:
    settings = update_automation_settings(
        request.app.state.database_path,
        enabled=payload.enabled,
        run_time=payload.run_time,
    )
    return settings
