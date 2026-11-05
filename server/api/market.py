"""市场数据底座 API：股票池 / 行情查询 / 同步触发与进度。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/symbols")
def get_symbols(request: Request, universe: str | None = None) -> list[dict]:
    return request.app.state.market_service.get_symbols(universe)


@router.get("/bars")
def get_bars(
    request: Request,
    symbol: str,
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    symbol = symbol.strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol cannot be empty")
    return request.app.state.market_service.get_symbol_bars(symbol, start=start, end=end)


@router.post("/sync")
def start_sync(request: Request, universe: str = "000300") -> dict:
    try:
        return request.app.state.market_service.start_sync(universe)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/sync/status")
def get_sync_status(request: Request, universe: str = "000300") -> dict:
    return request.app.state.market_service.get_sync_status(universe)
