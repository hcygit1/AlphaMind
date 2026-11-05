"""从 state JSON 的 markdown 决策字段提取结构化决策（纯函数，不碰数据库）。

state JSON 由 :meth:`alphamind.graph.trading_graph.AlphaMindGraph._log_state`
写入，其中 ``final_trade_decision`` 是 PM 决策、``trader_investment_decision``
是 Trader 提案，均为 :mod:`alphamind.agents.schemas` 渲染出的 markdown。
结构化输出降级为自由文本时字段会缺失，提取一律容忍（返回 None）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alphamind.agents.utils.rating import parse_rating

from server.trading.settings import DEFAULT_SETTLEMENT_DAYS

# PM 渲染格式：**Rating**: Buy / **Price Target**: 12.34 / **Time Horizon**: 3-6 months
# 中文降级输出：**最终评级：减持（Underweight）**
# Trader 渲染格式：**Action**: Buy / **Entry Price**: 12.34 / **Stop Loss**: 11.0
#                  / **Position Sizing**: 5% of portfolio
# 正则中的 \**\s* 容忍 markdown 加粗包裹的值；评级标签兼容中英文与中文冒号。
_RATING_RE = re.compile(r"(?:rating|评级).*?[:\-：][\s*]*(\w+)", re.IGNORECASE)
_ACTION_RE = re.compile(r"\*\*Action\*\*:\s*\**\s*(Buy|Hold|Sell)\b", re.IGNORECASE)
_FINAL_PROPOSAL_RE = re.compile(
    r"FINAL TRANSACTION PROPOSAL:\s*\**\s*(BUY|HOLD|SELL)\b", re.IGNORECASE
)
_ENTRY_PRICE_RE = re.compile(r"\*\*Entry Price\*\*:\s*\**\s*([\d.]+)")
_STOP_LOSS_RE = re.compile(r"\*\*Stop Loss\*\*:\s*\**\s*([\d.]+)")
_PRICE_TARGET_RE = re.compile(r"\*\*Price Target\*\*:\s*\**\s*([\d.]+)")
_TIME_HORIZON_RE = re.compile(r"\*\*Time Horizon\*\*:\s*\**\s*(.+)")
_POSITION_SIZING_RE = re.compile(r"\*\*Position Sizing\*\*:\s*\**\s*(.+)")
# 支持 "10%" 与区间 "5-10%"（捕获下限）
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)(?:\s*[-–~]\s*\d+(?:\.\d+)?)?\s*%")
# 支持 "6 months" 与区间 "3-6 months"（捕获下限）
_MONTH_RE = re.compile(
    r"(\d+(?:\.\d+)?)(?:\s*[-–~]\s*\d+(?:\.\d+)?)?\s*months?\b", re.IGNORECASE
)
_WEEK_RE = re.compile(
    r"(\d+(?:\.\d+)?)(?:\s*[-–~]\s*\d+(?:\.\d+)?)?\s*weeks?\b", re.IGNORECASE
)
_DAY_RE = re.compile(
    r"(\d+(?:\.\d+)?)(?:\s*[-–~]\s*\d+(?:\.\d+)?)?\s*days?\b", re.IGNORECASE
)

_TRADING_DAYS_PER_MONTH = 21
_TRADING_DAYS_PER_WEEK = 5


@dataclass
class DecisionRecord:
    """一条从投研结果提取出的结构化决策。"""

    rating: str  # 5-tier，保底 "Hold"
    action: str | None = None  # Buy / Hold / Sell，降级时 None
    entry_price: float | None = None
    stop_loss: float | None = None
    price_target: float | None = None
    position_pct: float | None = None  # 0.05 表示 5%
    time_horizon: str | None = None
    settlement_days: int = DEFAULT_SETTLEMENT_DAYS


def load_state(state_path: str | Path) -> dict[str, Any]:
    """读取 state JSON 文件。"""
    return json.loads(Path(state_path).read_text(encoding="utf-8"))


def parse_decision_from_state(
    state: dict[str, Any], fallback_rating: str = "Hold"
) -> DecisionRecord:
    """从 state JSON 提取决策。

    PM 决策缺失或降级为自由文本时，rating 回落到 ``fallback_rating``
    （调用方通常传报告 signal）。
    """
    pm_text = str(state.get("final_trade_decision") or "")
    trader_text = str(state.get("trader_investment_decision") or "")

    rating = fallback_rating
    if pm_text and _RATING_RE.search(pm_text):
        rating = parse_rating(pm_text, default=fallback_rating)

    time_horizon = _match_tail(pm_text, _TIME_HORIZON_RE)

    return DecisionRecord(
        rating=rating,
        action=_match_action(trader_text),
        entry_price=_match_price(trader_text, _ENTRY_PRICE_RE),
        stop_loss=_match_price(trader_text, _STOP_LOSS_RE),
        price_target=_match_price(pm_text, _PRICE_TARGET_RE),
        position_pct=_match_position_pct(trader_text),
        time_horizon=time_horizon,
        settlement_days=parse_settlement_days(time_horizon),
    )


def parse_settlement_days(time_horizon: str | None) -> int:
    """把 time_horizon（如 "3-6 months"）换算成交易日数。

    区间取下限（保守），无法解析返回默认 20 交易日。
    """
    if time_horizon:
        for pattern, unit_days in (
            (_MONTH_RE, _TRADING_DAYS_PER_MONTH),
            (_WEEK_RE, _TRADING_DAYS_PER_WEEK),
            (_DAY_RE, 1),
        ):
            m = pattern.search(time_horizon)
            if m:
                return max(1, round(float(m.group(1)) * unit_days))
    return DEFAULT_SETTLEMENT_DAYS


def _match_action(text: str) -> str | None:
    m = _ACTION_RE.search(text) or _FINAL_PROPOSAL_RE.search(text)
    return m.group(1).capitalize() if m else None


def _match_price(text: str, pattern: re.Pattern[str]) -> float | None:
    m = pattern.search(text)
    return float(m.group(1)) if m else None


def _match_tail(text: str, pattern: re.Pattern[str]) -> str | None:
    m = pattern.search(text)
    return m.group(1).strip().strip("*") if m else None


def _match_position_pct(text: str) -> float | None:
    m = _POSITION_SIZING_RE.search(text)
    if not m:
        return None
    pcts = [float(p) for p in _PCT_RE.findall(m.group(1))]
    if not pcts:
        return None
    return min(pcts) / 100.0
