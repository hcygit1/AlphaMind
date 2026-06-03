import json
from pathlib import Path

from server.db.connection import init_db
from server.db.repositories import upsert_default_identity
from server.services.report_service import (
    build_report_detail,
    extract_report_sections,
    index_report_file,
)


def test_index_report_file_and_build_detail(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)

    report_path = tmp_path / "300750" / "AlphaMindStrategy_logs" / "full_states_log_2026-06-03.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "company_of_interest": "300750",
                "trade_date": "2026-06-03",
                "market_report": "市场分析原文",
                "sentiment_report": "舆情分析原文",
                "news_report": "新闻分析原文",
                "fundamentals_report": "基本面分析原文",
                "policy_report": "政策分析原文",
                "hot_money_report": "资金流原文",
                "lockup_report": "解禁原文",
                "investment_debate_state": {"judge_decision": "多空结论"},
                "trader_investment_decision": "**Action**: Hold",
                "risk_debate_state": {"judge_decision": "风控结论"},
                "final_trade_decision": "**Rating**: Hold\n\n**Executive Summary**: 继续观察。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = index_report_file(db_path, report_path)
    assert report["ticker"] == "300750"
    assert report["signal"] == "Hold"
    assert report["summary"] == "继续观察。"

    detail = build_report_detail(db_path, report["id"])
    assert detail["report"]["id"] == report["id"]
    assert detail["sections"][0]["id"] == "market"
    assert detail["sections"][-1]["id"] == "final_decision"


def test_extract_report_sections_maps_existing_state_keys():
    sections = extract_report_sections(
        {
            "market_report": "市场",
            "investment_debate_state": {"judge_decision": "辩论"},
            "final_trade_decision": "最终",
        }
    )

    section_map = {section["id"]: section["raw"] for section in sections}
    assert section_map["market"] == "市场"
    assert section_map["debate"] == "辩论"
    assert section_map["final_decision"] == "最终"
