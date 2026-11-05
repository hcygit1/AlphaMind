"""Factor Lab API：因子注册表 / 评价执行 / 历史评价。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/factor", tags=["factor"])


class FactorEvalRequest(BaseModel):
    factor: str = Field(min_length=1)
    params: dict[str, Any] | None = None
    start: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


@router.get("/list")
def list_factors(request: Request) -> list[dict]:
    return request.app.state.factor_service.list_factors()


@router.post("/eval")
def evaluate_factor(request: Request, payload: FactorEvalRequest) -> dict:
    try:
        return request.app.state.factor_service.evaluate(
            payload.factor, payload.params, payload.start, payload.end
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/evals")
def list_evals(request: Request, factor: str | None = None) -> list[dict]:
    return request.app.state.factor_service.list_evals(factor)
