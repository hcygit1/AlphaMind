"""决策校验 Judge：可替换接口，v1 = RuleJudge（硬规则）+ LLMJudge（quick-LLM 软校验）。

判断结果连同 provider / 耗时落 judge_calls 表；将来接入 Jev 等决策模型时
实现同一接口即可对比分析（历史基线已在库中）。
"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from server.trading.extraction import DecisionRecord
from server.trading.settings import MAX_POSITION_PCT

VERDICT_PASS = "pass"
VERDICT_WARN = "warn"
VERDICT_BLOCK = "block"

_VERDICT_SEVERITY = {VERDICT_PASS: 0, VERDICT_WARN: 1, VERDICT_BLOCK: 2}

_RATING_DIRECTION = {
    "Buy": "buy",
    "Overweight": "buy",
    "Hold": "hold",
    "Underweight": "sell",
    "Sell": "sell",
}
_ACTION_DIRECTION = {"Buy": "buy", "Hold": "hold", "Sell": "sell"}


@dataclass
class JudgeResult:
    """一次 Judge 判断的结果。"""

    judge_name: str
    verdict: str  # pass / warn / block
    checks: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: int = 0
    provider: str | None = None

    def to_detail(self) -> dict[str, Any]:
        return {
            "judge_name": self.judge_name,
            "verdict": self.verdict,
            "provider": self.provider,
            "latency_ms": self.latency_ms,
            "checks": self.checks,
        }


class Judge(ABC):
    """可替换的决策校验接口。"""

    name: str = "judge"

    @abstractmethod
    def evaluate(self, decision: DecisionRecord, context: dict[str, Any] | None = None) -> JudgeResult:
        """校验一条决策。context 可携带 PM 决策原文等补充信息。"""


class RuleJudge(Judge):
    """硬规则校验：不调 LLM，确定性、毫秒级。

    - 评级与交易动作方向冲突 → warn
    - 买入且止损 ≥ 入场价 → block（逻辑错误，止损应在入场价下方）
    - 仓位超过单票上限 → warn（order_service 会按护栏截断）
    """

    name = "rule"

    def evaluate(self, decision: DecisionRecord, context: dict[str, Any] | None = None) -> JudgeResult:
        start = time.perf_counter()
        checks: list[dict[str, Any]] = []

        rating_dir = _RATING_DIRECTION.get(decision.rating)
        action_dir = _ACTION_DIRECTION.get(decision.action) if decision.action else None
        if rating_dir and action_dir and rating_dir != action_dir:
            checks.append({
                "name": "direction_conflict",
                "verdict": VERDICT_WARN,
                "message": f"评级 {decision.rating} 与交易动作 {decision.action} 方向冲突",
            })

        if (
            decision.action == "Buy"
            and decision.entry_price is not None
            and decision.stop_loss is not None
            and decision.stop_loss >= decision.entry_price
        ):
            checks.append({
                "name": "stop_loss_above_entry",
                "verdict": VERDICT_BLOCK,
                "message": f"止损价 {decision.stop_loss} 不低于入场价 {decision.entry_price}，买入逻辑错误",
            })

        if decision.position_pct is not None and decision.position_pct > MAX_POSITION_PCT:
            checks.append({
                "name": "position_over_limit",
                "verdict": VERDICT_WARN,
                "message": (
                    f"仓位 {decision.position_pct:.0%} 超过单票上限 {MAX_POSITION_PCT:.0%}，"
                    "下单时将按护栏截断"
                ),
            })

        verdict = max(
            (c["verdict"] for c in checks), key=lambda v: _VERDICT_SEVERITY[v], default=VERDICT_PASS
        )
        return JudgeResult(
            judge_name=self.name,
            verdict=verdict,
            checks=checks,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )


class LLMJudge(Judge):
    """quick-LLM 软校验：让小模型审视决策是否自洽、风险可控。

    LLM 输出无法解析时降级为 warn（不因模型抽风误伤，也不静默放行）。
    """

    name = "llm"

    def __init__(self, llm: Any, provider: str | None = None):
        self.llm = llm
        self.provider = provider

    def evaluate(self, decision: DecisionRecord, context: dict[str, Any] | None = None) -> JudgeResult:
        start = time.perf_counter()
        prompt = self._build_prompt(decision, context or {})
        try:
            content = str(self.llm.invoke(prompt).content)
            verdict, reason = self._parse(content)
            checks = [{"name": "llm_review", "verdict": verdict, "message": reason}]
        except Exception as exc:
            verdict = VERDICT_WARN
            checks = [{"name": "llm_review", "verdict": verdict, "message": f"LLM 调用失败: {exc}"}]

        return JudgeResult(
            judge_name=self.name,
            verdict=verdict,
            checks=checks,
            latency_ms=int((time.perf_counter() - start) * 1000),
            provider=self.provider,
        )

    def _build_prompt(self, decision: DecisionRecord, context: dict[str, Any]) -> str:
        lines = [
            "你是一名 A 股交易合规审查员。审查以下交易决策是否合理、自洽、风险可控。",
            "",
            f"评级: {decision.rating}",
            f"交易动作: {decision.action or '未知'}",
            f"入场价: {decision.entry_price or '未给出'}",
            f"止损价: {decision.stop_loss or '未给出'}",
            f"目标价: {decision.price_target or '未给出'}",
            f"仓位: {f'{decision.position_pct:.0%}' if decision.position_pct else '未给出'}",
            f"持有期: {decision.time_horizon or '未给出'}",
        ]
        pm_decision = str(context.get("pm_decision") or "")
        if pm_decision:
            lines.extend(["", "PM 决策原文:", pm_decision])
        lines.extend([
            "",
            "检查：评级与动作是否一致、止损/目标价与入场价关系是否合理、"
            "仓位与持有期是否匹配、有无明显逻辑矛盾或遗漏的关键风险。",
            '只输出 JSON：{"verdict": "pass" | "warn" | "block", "reason": "一句话理由"}',
        ])
        return "\n".join(lines)

    @staticmethod
    def _parse(content: str) -> tuple[str, str]:
        try:
            data = json.loads(content)
            verdict = str(data.get("verdict", "")).lower()
            reason = str(data.get("reason", ""))
            if verdict in _VERDICT_SEVERITY:
                return verdict, reason or "LLM 未给出理由"
        except (json.JSONDecodeError, AttributeError):
            pass
        m = re.search(r"\b(pass|warn|block)\b", content.lower())
        if m:
            return m.group(1), content.strip()[:200]
        return VERDICT_WARN, f"LLM 输出无法解析: {content[:200]}"
