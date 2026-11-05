"""价量因子库：基于收盘价/成交量面板的横截面因子。

统一签名：``func(close, volume, **params) -> DataFrame``
输入输出均为 date × symbol 面板（index 为 YYYY-MM-DD 字符串）。
"""
from __future__ import annotations

from typing import Any, Callable

import pandas as pd

FactorFn = Callable[..., pd.DataFrame]


def momentum(close: pd.DataFrame, volume: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """N 日动量：区间收益率，高值代表近期涨幅大。"""
    return close.pct_change(window)


def reversal(close: pd.DataFrame, volume: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """短期反转：负动量，高值代表近期跌幅大。"""
    return -close.pct_change(window)


def volatility(close: pd.DataFrame, volume: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """N 日波动率：日收益率标准差，高值代表波动剧烈。"""
    return close.pct_change().rolling(window).std()


def volume_ratio(close: pd.DataFrame, volume: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """量比：当日成交量 / N 日均量，高值代表放量。"""
    return volume / volume.rolling(window).mean()


def corr_price_vol(close: pd.DataFrame, volume: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """N 日价量相关系数，高值代表量价同涨同跌。"""
    return close.rolling(window).corr(volume)


def bias(close: pd.DataFrame, volume: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """N 日乖离率：(收盘价 - 均价) / 均价，高值代表价格偏离均线。"""
    ma = close.rolling(window).mean()
    return (close - ma) / ma


# 因子注册表：key -> {func, default_params, description}
FACTOR_DEFS: dict[str, dict[str, Any]] = {
    "momentum": {
        "func": momentum,
        "default_params": {"window": 20},
        "description": "N 日动量（区间收益率），高值代表近期涨幅大",
    },
    "reversal": {
        "func": reversal,
        "default_params": {"window": 5},
        "description": "短期反转（负动量），高值代表近期跌幅大",
    },
    "volatility": {
        "func": volatility,
        "default_params": {"window": 20},
        "description": "N 日波动率（日收益标准差），高值代表波动剧烈",
    },
    "volume_ratio": {
        "func": volume_ratio,
        "default_params": {"window": 20},
        "description": "量比：当日成交量 / N 日均量，高值代表放量",
    },
    "corr_price_vol": {
        "func": corr_price_vol,
        "default_params": {"window": 20},
        "description": "N 日价量相关系数，高值代表量价同涨同跌",
    },
    "bias": {
        "func": bias,
        "default_params": {"window": 20},
        "description": "N 日乖离率：(收盘价-均价)/均价，高值代表偏离均线",
    },
}
