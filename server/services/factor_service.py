"""Factor Lab 编排：面板加载 + 因子评价 + 结果落库。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from alphamind.factors import FACTOR_DEFS, evaluate_factor
from server.db.repositories import fetch_all_bars, list_factor_evals, save_factor_eval

logger = logging.getLogger(__name__)


class FactorService:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    def list_factors(self) -> list[dict[str, Any]]:
        """因子注册表（key + 默认参数 + 描述）。"""
        return [
            {
                "key": key,
                "default_params": meta["default_params"],
                "description": meta["description"],
            }
            for key, meta in FACTOR_DEFS.items()
        ]

    def evaluate(
        self,
        factor_key: str,
        params: dict[str, Any] | None = None,
        start: str | None = None,
        end: str | None = None,
        universe: str = "000300",
    ) -> dict[str, Any]:
        """执行因子评价：加载面板 → 算因子 → IC/分层 → 落库。"""
        meta = FACTOR_DEFS.get(factor_key)
        if meta is None:
            raise KeyError(f"未知因子: {factor_key}")
        merged_params = {**meta["default_params"], **(params or {})}

        rows = fetch_all_bars(self.db_path, start=start, end=end)
        if not rows:
            raise ValueError("库中无行情数据，请先执行市场数据同步")

        df = pd.DataFrame(rows)
        close = df.pivot(index="date", columns="symbol", values="close").sort_index()
        volume = df.pivot(index="date", columns="symbol", values="volume").sort_index()

        result = evaluate_factor(close, volume, meta["func"], merged_params)
        eval_row = save_factor_eval(
            self.db_path,
            factor_key,
            merged_params,
            universe,
            start or close.index[0],
            end or close.index[-1],
            result["summary"],
        )
        logger.info(
            "因子评价完成: %s%s ic_mean=%s icir=%s",
            factor_key,
            merged_params,
            result["summary"]["ic_mean"],
            result["summary"]["icir"],
        )
        return {
            "eval_id": eval_row["id"],
            "factor": factor_key,
            "params": merged_params,
            "start_date": eval_row["start_date"],
            "end_date": eval_row["end_date"],
            **result,
        }

    def list_evals(self, factor_key: str | None = None) -> list[dict[str, Any]]:
        return list_factor_evals(self.db_path, factor_key=factor_key)
