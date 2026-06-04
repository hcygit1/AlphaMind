"""Simple first-pass intent router."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Intent:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


class IntentRouter:
    def route(self, message: str) -> Intent:
        text = message.strip().lower()
        if any(keyword in text for keyword in ("深度分析", "投研", "分析一下")):
            return Intent(name="deep_research", arguments={"message": message})
        if any(keyword in text for keyword in ("总结", "报告", "最终决策", "风控")):
            return Intent(name="report_summary", arguments={})
        return Intent(name="chat", arguments={})
