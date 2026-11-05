"""Strategy Lab 编排：面板加载 + 规则回测 + 结果落库。"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from alphamind.strategies import STRATEGY_TEMPLATES, run_backtest, validate_rules
from server.db.repositories import (
    fetch_all_bars,
    get_strategy_run,
    list_strategy_runs,
    save_strategy_run,
)

logger = logging.getLogger(__name__)


class StrategyService:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    def list_templates(self) -> list[dict[str, Any]]:
        """内置策略模板（key + 名称 + 描述 + 规则）。"""
        return [
            {"key": key, **meta}
            for key, meta in STRATEGY_TEMPLATES.items()
        ]

    def backtest(
        self,
        name: str,
        rules: dict[str, Any],
        start: str | None = None,
        end: str | None = None,
        universe: str = "000300",
    ) -> dict[str, Any]:
        """执行策略回测：校验规则 → 加载面板 → 回测 → 落库。"""
        validate_rules(rules)

        rows = fetch_all_bars(self.db_path, start=start, end=end)
        if not rows:
            raise ValueError("库中无行情数据，请先执行市场数据同步")

        df = pd.DataFrame(rows)
        close = df.pivot(index="date", columns="symbol", values="close").sort_index()
        volume = df.pivot(index="date", columns="symbol", values="volume").sort_index()

        result = run_backtest(close, volume, rules)
        run_row = save_strategy_run(
            self.db_path,
            name,
            rules,
            universe,
            start or close.index[0],
            end or close.index[-1],
            result["metrics"],
            {
                "nav_curve": result["nav_curve"],
                "periods": result["periods"],
                "n_limit_up_blocked": result["metrics"].get("n_limit_up_blocked"),
            },
        )
        logger.info(
            "策略回测完成: %s n_periods=%s annual_return=%s benchmark=%s",
            name,
            result["metrics"]["n_periods"],
            result["metrics"]["annual_return"],
            result["metrics"]["benchmark_annual_return"],
        )
        return {
            "run_id": run_row["id"],
            "name": name,
            "rules": rules,
            "start_date": run_row["start_date"],
            "end_date": run_row["end_date"],
            "created_at": run_row["created_at"],
            **result,
        }

    def list_runs(self, name: str | None = None) -> list[dict[str, Any]]:
        runs = list_strategy_runs(self.db_path, name=name)
        for r in runs:
            r["rules"] = self._loads(r.get("rules"))
        return runs

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        run = get_strategy_run(self.db_path, run_id)
        if run is None:
            return None
        run["rules"] = self._loads(run.get("rules"))
        run["detail"] = self._loads(run.get("detail"))
        return run

    @staticmethod
    def _loads(raw: str | dict | None) -> Any:
        if isinstance(raw, str):
            return json.loads(raw)
        return raw
