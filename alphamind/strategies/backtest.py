"""规则型策略回测引擎：筛选 → 排序 → Top N 等权持有，月度调仓。

策略规则（JSON 可序列化）：
    {
      "rank_by": "reversal",            # 排序因子（必填，须在 FACTOR_DEFS 中）
      "rank_params": {"window": 10},    # 排序因子参数（覆盖默认）
      "rank_ascending": true,           # 因子值小者优先（默认 true）
      "filters": [                       # 预筛选（可选，多条件取交集）
        {"factor": "volatility", "params": {"window": 20}, "op": "lt", "threshold": 0.04}
      ],
      "top_n": 10                        # 持仓数量（必填，1-50）
    }
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from alphamind.factors.price_volume import FACTOR_DEFS

DEFAULT_FEE_RATE = 0.001  # 单边佣金万十（0.1%）
MIN_SAMPLES = 10          # 单期可选股票数下限，不足则当期空仓
PERIODS_PER_YEAR = 12

_FILTER_OPS = {
    "gt": lambda s, t: s > t,
    "lt": lambda s, t: s < t,
}

# 内置策略模板（开箱即用 + 前端示例）
STRATEGY_TEMPLATES: dict[str, dict[str, Any]] = {
    "reversal_top10": {
        "name": "反转 Top10",
        "description": "买入近 10 日跌幅最大的 10 只（A 股反转效应）",
        "rules": {
            "rank_by": "reversal",
            "rank_params": {"window": 10},
            "rank_ascending": False,
            "top_n": 10,
        },
    },
    "low_vol_top20": {
        "name": "低波动 Top20",
        "description": "买入 20 日波动率最低的 20 只（低波异象）",
        "rules": {
            "rank_by": "volatility",
            "rank_ascending": True,
            "top_n": 20,
        },
    },
    "decouple_top15": {
        "name": "量价背离 Top15",
        "description": "买入价量相关性最低的 15 只（价量背离）",
        "rules": {
            "rank_by": "corr_price_vol",
            "rank_ascending": True,
            "top_n": 15,
        },
    },
}


def validate_rules(rules: dict[str, Any]) -> None:
    """校验策略规则，非法即抛 ValueError。"""
    rank_by = rules.get("rank_by")
    if rank_by not in FACTOR_DEFS:
        raise ValueError(f"未知排序因子: {rank_by}")
    top_n = rules.get("top_n")
    if not isinstance(top_n, int) or not (1 <= top_n <= 50):
        raise ValueError("top_n 必须为 1-50 的整数")
    for f in rules.get("filters") or []:
        if f.get("factor") not in FACTOR_DEFS:
            raise ValueError(f"未知筛选因子: {f.get('factor')}")
        if f.get("op") not in _FILTER_OPS:
            raise ValueError(f"筛选 op 只支持 {list(_FILTER_OPS)}，得到: {f.get('op')}")
        if "threshold" not in f:
            raise ValueError("筛选条件缺少 threshold")


def _rebalance_dates(dates: pd.Index) -> list[str]:
    """每月最后一个交易日。"""
    last_of_month: dict[str, str] = {}
    for d in dates:
        last_of_month[str(d)[:7]] = d
    return [last_of_month[m] for m in sorted(last_of_month)]


def _factor_panel(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    factor_key: str,
    params: dict[str, Any] | None,
) -> pd.DataFrame:
    meta = FACTOR_DEFS[factor_key]
    merged = {**meta["default_params"], **(params or {})}
    return meta["func"](close, volume, **merged)


def run_backtest(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    rules: dict[str, Any],
    fee_rate: float = DEFAULT_FEE_RATE,
) -> dict[str, Any]:
    """执行规则型策略回测（月度调仓，等权持仓，双边佣金）。

    A 股成交约束：调仓日当日涨停（主板 ≥9.8%、创业板/科创板 ≥19.8%）的
    股票视为买不进，从当期候选中剔除（卖出侧跌停卖不出暂不处理）。

    Returns:
        {
          "metrics": {n_periods, annual_return, annual_vol, sharpe,
                      max_drawdown, win_rate, avg_turnover,
                      benchmark_annual_return, n_limit_up_blocked},
          "nav_curve": {"dates": [...], "nav": [...], "benchmark_nav": [...]},
          "periods": [{date, holdings, ret, turnover, cost}, ...],
        }
    """
    validate_rules(rules)
    rebalance = _rebalance_dates(close.index)
    fwd = close.loc[rebalance].pct_change().shift(-1)

    # 涨停阈值：主板 10%，创业板/科创板 20%（留 0.2% 容忍前复权舍入误差）
    daily_ret = close.pct_change()
    limit_up = pd.Series(
        [0.198 if str(s)[:3] in ("300", "301", "688") else 0.098 for s in close.columns],
        index=close.columns,
    )

    rank_values = _factor_panel(
        close, volume, rules["rank_by"], rules.get("rank_params")
    ).loc[rebalance]
    filter_panels = [
        (
            _factor_panel(close, volume, f["factor"], f.get("params")).loc[rebalance],
            _FILTER_OPS[f["op"]],
            f["threshold"],
        )
        for f in rules.get("filters") or []
    ]

    ascending = rules.get("rank_ascending", True)
    top_n: int = rules["top_n"]

    # 全池等权基准
    def _benchmark_ret(d: str) -> float:
        r = fwd.loc[d].dropna()
        return float(r.mean()) if len(r) else 0.0

    periods: list[dict[str, Any]] = []
    prev_holdings: set[str] = set()
    nav, bench_nav = 1.0, 1.0
    n_blocked = 0
    nav_curve: dict[str, list[Any]] = {"dates": [], "nav": [1.0], "benchmark_nav": [1.0]}

    for d in rebalance[:-1]:
        candidates = rank_values.loc[d].dropna()
        for panel, op, threshold in filter_panels:
            fv = op(panel.loc[d], threshold).dropna()
            candidates = candidates[candidates.index.isin(fv.index)]
        # 涨停买不进：剔除调仓日当日已封板的候选
        day_ret = daily_ret.loc[d].reindex(candidates.index)
        blocked = (day_ret >= limit_up.reindex(candidates.index)).fillna(False)
        n_blocked += int(blocked.sum())
        candidates = candidates[~blocked]
        if len(candidates) < MIN_SAMPLES:
            holdings: list[str] = []
        else:
            holdings = candidates.sort_values(ascending=ascending).head(top_n).index.tolist()

        r = fwd.loc[d]
        valid = [s for s in holdings if not pd.isna(r[s])]
        gross = float(r[valid].mean()) if valid else 0.0
        turnover = 1.0 if not prev_holdings and holdings else (
            len(set(holdings) - prev_holdings) / len(holdings) if holdings else 0.0
        )
        cost = turnover * 2 * fee_rate  # 换仓部分双边佣金
        net = gross - cost

        prev_holdings = set(holdings)
        nav *= 1 + net
        bench_nav *= 1 + _benchmark_ret(d)
        nav_curve["dates"].append(d)
        nav_curve["nav"].append(nav)
        nav_curve["benchmark_nav"].append(bench_nav)
        periods.append(
            {"date": d, "holdings": holdings, "ret": net, "turnover": turnover, "cost": cost}
        )

    returns = pd.Series([p["ret"] for p in periods], dtype=float)
    n = len(returns)
    nav_series = pd.Series(nav_curve["nav"])
    cummax = nav_series.cummax()

    metrics: dict[str, Any] = {
        "n_periods": n,
        "annual_return": float(nav ** (PERIODS_PER_YEAR / n) - 1) if n and nav > 0 else -1.0,
        "annual_vol": float(returns.std() * (PERIODS_PER_YEAR ** 0.5)) if n else None,
        "sharpe": None,
        "max_drawdown": float((nav_series / cummax - 1).min()) if n else None,
        "win_rate": float((returns > 0).mean()) if n else None,
        "avg_turnover": float(pd.Series([p["turnover"] for p in periods]).mean()) if n else None,
        "benchmark_annual_return": (
            float(bench_nav ** (PERIODS_PER_YEAR / n) - 1) if n and bench_nav > 0 else -1.0
        ),
        "n_limit_up_blocked": n_blocked,
    }
    if n and metrics["annual_vol"] and metrics["annual_vol"] > 0:
        metrics["sharpe"] = float(returns.mean() / returns.std() * (PERIODS_PER_YEAR ** 0.5))
    return {"metrics": metrics, "nav_curve": nav_curve, "periods": periods}
