"""Report indexing and detail rendering helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from alphamind.agents.utils.rating import parse_rating
from server.db.repositories import get_report, upsert_report


SECTION_DEFS = [
    ("market", "市场分析", "market_report"),
    ("sentiment", "舆情分析", "sentiment_report"),
    ("news", "新闻分析", "news_report"),
    ("fundamentals", "基本面分析", "fundamentals_report"),
    ("policy", "政策分析", "policy_report"),
    ("hot_money", "游资/资金流", "hot_money_report"),
    ("lockup", "解禁/减持", "lockup_report"),
    ("debate", "多空辩论", "investment_debate_state"),
    ("trader", "交易计划", "trader_investment_decision"),
    ("risk", "风控辩论", "risk_debate_state"),
    ("final_decision", "最终决策", "final_trade_decision"),
]


def load_state(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_signal(state: dict[str, Any]) -> str:
    text = str(state.get("final_trade_decision", ""))
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return parse_rating(cleaned)


def extract_summary(state: dict[str, Any]) -> str:
    text = str(state.get("final_trade_decision", ""))
    match = re.search(r"\*\*Executive Summary\*\*:\s*(.+)", text)
    if match:
        return match.group(1).strip()
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned[:180] if cleaned else "暂无摘要"


def _raw_section(state: dict[str, Any], key: str) -> str:
    value = state.get(key, "")
    if isinstance(value, dict):
        return str(value.get("judge_decision") or value.get("history") or value)
    return str(value)


def extract_report_sections(state: dict[str, Any]) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    for section_id, title, key in SECTION_DEFS:
        raw = _raw_section(state, key)
        sections.append(
            {
                "id": section_id,
                "title": title,
                "summary": raw[:220] if raw else "暂无内容",
                "raw": raw,
            }
        )
    return sections


def index_report_file(db_path: str | Path, state_path: str | Path) -> dict[str, Any]:
    path = Path(state_path)
    state = load_state(path)
    ticker = str(state.get("company_of_interest") or path.parent.parent.name)
    trade_date = str(state.get("trade_date") or path.stem.replace("full_states_log_", ""))
    return upsert_report(
        db_path,
        ticker=ticker,
        trade_date=trade_date,
        signal=extract_signal(state),
        summary=extract_summary(state),
        state_path=str(path),
    )


def build_report_detail(db_path: str | Path, report_id: str) -> dict[str, Any]:
    report = get_report(db_path, report_id)
    if not report:
        return {}
    state = load_state(report["state_path"])
    return {
        "report": report,
        "sections": extract_report_sections(state),
        "state": state,
    }
