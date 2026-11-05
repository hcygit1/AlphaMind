"""因子评价引擎：IC 分析 + 分层回测（月度调仓）。

流程：
1. 每月最后一个交易日为调仓日，取当日因子值做横截面
2. IC = 当期因子值与下期收益的 Spearman 秩相关
3. 分层回测：当期按因子值五等分组（Q1 最低 ~ Q5 最高），各组等权持有至下期
"""
from __future__ import annotations

from typing import Any, Callable

import pandas as pd

MIN_SAMPLES = 20        # 单期有效样本下限（不足则跳过该期）
N_QUANTILES = 5         # 分层数
PERIODS_PER_YEAR = 12   # 月度调仓的年化系数

FactorFn = Callable[..., pd.DataFrame]


def _annualize(returns: pd.Series) -> float | None:
    """月收益序列 → 复利年化收益。"""
    if len(returns) == 0:
        return None
    nav = float((1 + returns).prod())
    if nav <= 0:
        return -1.0  # 累计净值归零（破产），年化记 -100%
    return nav ** (PERIODS_PER_YEAR / len(returns)) - 1


def _rebalance_dates(dates: pd.Index) -> list[str]:
    """每月最后一个交易日。"""
    last_of_month: dict[str, str] = {}
    for d in dates:
        last_of_month[str(d)[:7]] = d
    return [last_of_month[m] for m in sorted(last_of_month)]


def evaluate_factor(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    factor_fn: FactorFn,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """评价单个因子，返回 IC 统计 + 分层净值曲线。

    Returns:
        {
          "summary": {n_periods, ic_mean, ic_std, icir, win_rate,
                      long_short_annual, quantile_annuals},
          "ic_series": [{date, ic}, ...],
          "quantile": {"dates": [...], "navs": {"Q1": [...], ...}},
          "long_short_nav": [...],
        }
    """
    fv = factor_fn(close, volume, **(params or {}))
    rebalance = _rebalance_dates(close.index)

    # 下期收益：第 i 行 = 调仓日 d_i → d_{i+1} 的区间收益
    fwd = close.loc[rebalance].pct_change().shift(-1)
    fv_rb = fv.loc[rebalance]

    records: list[dict[str, Any]] = []
    for d in rebalance[:-1]:
        f = fv_rb.loc[d]
        r = fwd.loc[d]
        valid = f.dropna().index.intersection(r.dropna().index)
        if len(valid) < MIN_SAMPLES:
            continue
        f, r = f[valid], r[valid]
        # Spearman 秩相关 = 秩变换后的 Pearson（免 scipy 依赖）
        ic = f.rank().corr(r.rank())
        if pd.isna(ic):
            continue
        row: dict[str, Any] = {"date": d, "ic": float(ic)}
        try:
            q = pd.qcut(f, N_QUANTILES, labels=False, duplicates="drop")
            if q.nunique() == N_QUANTILES:
                for g in range(N_QUANTILES):
                    row[f"Q{g + 1}"] = float(r[q == g].mean())
                row["LS"] = row[f"Q{N_QUANTILES}"] - row["Q1"]
        except ValueError:
            pass  # 因子值几乎全相同，无法分层，仅保留 IC
        records.append(row)

    ic_series = pd.Series([r["ic"] for r in records], dtype=float)
    layered = [r for r in records if "Q1" in r]

    # 分层净值曲线（各期等权持有，含期初 1.0）
    nav_dates = [r["date"] for r in layered]
    navs: dict[str, list[float]] = {f"Q{g + 1}": [1.0] for g in range(N_QUANTILES)}
    ls_nav = [1.0]
    for r in layered:
        for g in range(N_QUANTILES):
            navs[f"Q{g + 1}"].append(navs[f"Q{g + 1}"][-1] * (1 + r[f"Q{g + 1}"]))
        ls_nav.append(ls_nav[-1] * (1 + r["LS"]))

    quantile_annuals: dict[str, float | None] = {}
    for g in range(N_QUANTILES):
        key = f"Q{g + 1}"
        quantile_annuals[key] = _annualize(pd.Series([r[key] for r in layered]))
    ls_returns = pd.Series([r["LS"] for r in layered])

    summary = {
        "n_periods": len(records),
        "ic_mean": float(ic_series.mean()) if len(ic_series) else None,
        "ic_std": float(ic_series.std()) if len(ic_series) else None,
        "icir": float(ic_series.mean() / ic_series.std()) if len(ic_series) and ic_series.std() > 0 else None,
        "win_rate": float((ic_series > 0).mean()) if len(ic_series) else None,
        "long_short_annual": _annualize(ls_returns),
        "quantile_annuals": quantile_annuals,
    }
    return {
        "summary": summary,
        "ic_series": [{"date": r["date"], "ic": r["ic"]} for r in records],
        "quantile": {"dates": nav_dates, "navs": navs},
        "long_short_nav": ls_nav,
    }
