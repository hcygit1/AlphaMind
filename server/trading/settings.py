"""交易闭环常量：费率、护栏阈值、默认仓位。环境变量可覆盖。"""

from __future__ import annotations

import os


def _env_float(name: str, default: str) -> float:
    return float(os.getenv(name, default))


def _env_int(name: str, default: str) -> int:
    return int(os.getenv(name, default))


# 模拟账户初始资金（元）
INITIAL_CASH = _env_float("ALPHAMIND_INITIAL_CASH", "1000000")

# 佣金：万 2.5，单笔最低 5 元；印花税：卖出千 1；过户费暂不计
COMMISSION_RATE = _env_float("ALPHAMIND_COMMISSION_RATE", "0.00025")
COMMISSION_MIN = _env_float("ALPHAMIND_COMMISSION_MIN", "5")
STAMP_TAX_SELL = _env_float("ALPHAMIND_STAMP_TAX_SELL", "0.001")

# A 股一手 100 股
LOT_SIZE = _env_int("ALPHAMIND_LOT_SIZE", "100")

# 决策缺 position_sizing 时按评级给默认仓位（占净值比例）；Hold 不下单
DEFAULT_POSITION_PCT: dict[str, float] = {
    "Buy": 0.10,
    "Overweight": 0.05,
    "Sell": 0.10,
    "Underweight": 0.05,
}

# 护栏：单票 ≤ 20% 净值，总仓位 ≤ 90%，日亏损 > 5% 暂停新买入
MAX_POSITION_PCT = _env_float("ALPHAMIND_MAX_POSITION_PCT", "0.20")
MAX_TOTAL_POSITION_PCT = _env_float("ALPHAMIND_MAX_TOTAL_POSITION_PCT", "0.90")
DAILY_LOSS_HALT_PCT = _env_float("ALPHAMIND_DAILY_LOSS_HALT_PCT", "0.05")

# 结算窗口（交易日）：time_horizon 无法解析时的默认值
DEFAULT_SETTLEMENT_DAYS = _env_int("ALPHAMIND_DEFAULT_SETTLEMENT_DAYS", "20")
