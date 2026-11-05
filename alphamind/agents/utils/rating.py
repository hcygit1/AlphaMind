"""Shared 5-tier rating vocabulary and a deterministic heuristic parser.

The same five-tier scale (Buy, Overweight, Hold, Underweight, Sell) is used by:
- The Research Manager (investment plan recommendation)
- The Portfolio Manager (final position decision)
- The signal processor (rating extracted for downstream consumers)
- The memory log (rating tag stored alongside each decision entry)

Centralising it here avoids drift between those call sites.
"""

from __future__ import annotations

import re
from typing import Tuple


# Canonical, ordered 5-tier scale (most bullish to most bearish).
RATINGS_5_TIER: Tuple[str, ...] = (
    "Buy", "Overweight", "Hold", "Underweight", "Sell",
)

_RATING_SET = {r.lower() for r in RATINGS_5_TIER}

# 中文输出（output_language=Chinese）时 LLM 使用的评级词 → 5-tier
_RATING_ALIASES = {
    "买入": "Buy",
    "增持": "Overweight",
    "超配": "Overweight",
    "持有": "Hold",
    "中性": "Hold",
    "减持": "Underweight",
    "低配": "Underweight",
    "卖出": "Sell",
    "清仓": "Sell",
}

# 词两侧可能包裹的装饰字符（markdown 加粗、中英文括号、标点）
_WORD_STRIP = "*:.,（）()【】[]「」"

# Matches "Rating: X" / "评级：X" / "Rating: **X**" — tolerates markdown
# bold wrappers, Chinese labels/colons, and either a colon or hyphen separator.
_RATING_LABEL_RE = re.compile(r"(?:rating|评级).*?[:\-：][\s*]*(\w+)", re.IGNORECASE)


def _canonical(word: str) -> str | None:
    """英文 5-tier 词或中文评级别名 → 规范评级词；无法识别返回 None。"""
    w = word.strip(_WORD_STRIP)
    if w.lower() in _RATING_SET:
        return w.capitalize()
    return _RATING_ALIASES.get(w)


# 第二趟兜底分词：连续英文字母段或连续汉字段（中文无空格分词）
_TOKEN_RE = re.compile(r"[A-Za-z]+|[\u4e00-\u9fff]+")


def parse_rating(text: str, default: str = "Hold") -> str:
    """Heuristically extract a 5-tier rating from prose text.

    Two-pass strategy:
    1. Look for an explicit "Rating: X" / "评级：X" label (tolerant of markdown
       bold and Chinese aliases like 减持).
    2. Fall back to the first 5-tier rating word found anywhere in the text.

    Returns a Title-cased rating string, or ``default`` if no rating word appears.
    """
    for line in text.splitlines():
        m = _RATING_LABEL_RE.search(line)
        if m:
            canonical = _canonical(m.group(1))
            if canonical:
                return canonical

    for line in text.splitlines():
        for token in _TOKEN_RE.findall(line):
            canonical = _canonical(token)
            if canonical:
                return canonical

    return default
