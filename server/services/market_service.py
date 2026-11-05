"""市场数据底座：成分股同步 + 日线行情落库编排。"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from alphamind.dataflows.a_stock import fetch_daily_bars, get_index_constituents
from server.db.repositories import (
    create_sync_run, get_bars, get_latest_sync_run,
    get_market_stats, list_stock_meta, update_sync_run, upsert_bars, upsert_stock_meta,
)

logger = logging.getLogger(__name__)

DEFAULT_UNIVERSE = "000300"  # 沪深300
SYNC_START_DATE = "2018-01-01"  # 首次全量回补起点


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class MarketService:
    """后台 daemon 线程执行同步，进度与结果落库 market_sync_runs。"""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()

    # ---- 同步 ----

    def start_sync(self, universe: str = DEFAULT_UNIVERSE) -> dict[str, Any]:
        with self._lock:
            latest = get_latest_sync_run(self.db_path, universe)
            if latest and latest.get("status") == "running":
                raise ValueError("同步正在进行中，请等待完成后再试")
            run = create_sync_run(self.db_path, universe, total_symbols=0)

        threading.Thread(
            target=self._run_sync, args=(run["id"], universe), daemon=True
        ).start()
        return run

    def _run_sync(self, run_id: str, universe: str) -> None:
        failed: list[str] = []
        try:
            constituents = get_index_constituents(universe)
            rows = constituents.to_dict("records")
            update_sync_run(self.db_path, run_id, total_symbols=len(rows))
            upsert_stock_meta(self.db_path, universe, rows)

            for i, row in enumerate(rows):
                symbol = row["symbol"]
                try:
                    self._sync_symbol(symbol)
                except Exception as exc:
                    failed.append(symbol)
                    logger.warning("同步 %s 失败: %s", symbol, exc)
                update_sync_run(self.db_path, run_id, done_symbols=i + 1)
                time.sleep(0.4)  # 限速：连续快速请求会触发东财频控断连

            update_sync_run(
                self.db_path,
                run_id,
                status="completed",
                failed_symbols=",".join(failed),
                finished_at=_utc_now(),
            )
            logger.info(
                "市场数据同步完成: universe=%s total=%d failed=%d",
                universe,
                len(rows),
                len(failed),
            )
        except Exception as exc:
            logger.exception("市场数据同步失败: %s", exc)
            update_sync_run(
                self.db_path,
                run_id,
                status="failed",
                error_message=str(exc),
                finished_at=_utc_now(),
            )

    def _sync_symbol(self, symbol: str) -> int:
        """单只股票全量拉取（前复权）并整体替换落库，返回写入行数。

        前复权价格在除权除息后会全历史变化，因此每次全量拉取 +
        INSERT OR REPLACE 整体替换，保证复权一致性。
        """
        df = fetch_daily_bars(symbol, start_date=SYNC_START_DATE)
        if df.empty:
            return 0

        bars = []
        for row in df.itertuples(index=False):
            amount = row.Amount
            bars.append(
                {
                    "date": row.Date.strftime("%Y-%m-%d"),
                    "open": float(row.Open),
                    "high": float(row.High),
                    "low": float(row.Low),
                    "close": float(row.Close),
                    "volume": float(row.Volume),
                    "amount": float(amount) if pd.notna(amount) else None,
                }
            )
        return upsert_bars(self.db_path, symbol, bars)

    # ---- 查询 ----

    def get_symbols(self, universe: str | None = None) -> list[dict[str, Any]]:
        return list_stock_meta(self.db_path, universe)

    def get_symbol_bars(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_bars(self.db_path, symbol, start=start, end=end)

    def get_sync_status(self, universe: str = DEFAULT_UNIVERSE) -> dict[str, Any]:
        return {
            "run": get_latest_sync_run(self.db_path, universe),
            "stats": get_market_stats(self.db_path),
        }
