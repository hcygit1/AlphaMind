"""决策提取（state JSON → DecisionRecord）与交易仓库的单元测试。"""

from pathlib import Path

from server.db.connection import init_db
from server.db.repositories import upsert_default_identity, upsert_report
from server.db.trading_repositories import (
    create_decision,
    get_decision_by_report,
    get_or_create_default_account,
)
from server.trading.extraction import (
    DecisionRecord,
    load_state,
    parse_decision_from_state,
    parse_settlement_days,
)
from server.trading.settings import INITIAL_CASH


def make_state(
    pm: str = "",
    trader: str = "",
) -> dict:
    return {"final_trade_decision": pm, "trader_investment_decision": trader}


FULL_PM = (
    "**Rating**: Buy\n\n"
    "**Executive Summary**: 建议分批建仓。\n\n"
    "**Investment Thesis**: 动能延续。\n\n"
    "**Price Target**: 245.5\n\n"
    "**Time Horizon**: 3-6 months"
)
FULL_TRADER = (
    "**Action**: Buy\n\n"
    "**Reasoning**: 突破确认。\n\n"
    "**Entry Price**: 230.5\n\n"
    "**Stop Loss**: 215.0\n\n"
    "**Position Sizing**: 10% of portfolio\n\n"
    "FINAL TRANSACTION PROPOSAL: **BUY**"
)


def test_parse_decision_full_fields():
    record = parse_decision_from_state(make_state(FULL_PM, FULL_TRADER))

    assert record.rating == "Buy"
    assert record.action == "Buy"
    assert record.entry_price == 230.5
    assert record.stop_loss == 215.0
    assert record.price_target == 245.5
    assert record.position_pct == 0.10
    assert record.time_horizon == "3-6 months"
    assert record.settlement_days == 63  # 3 个月 × 21


def test_parse_decision_missing_optional_fields():
    pm = "**Rating**: Hold\n\n**Executive Summary**: 观察。"
    trader = "**Action**: Hold\n\n**Reasoning**: 证据均衡。"

    record = parse_decision_from_state(make_state(pm, trader))

    assert record.rating == "Hold"
    assert record.action == "Hold"
    assert record.entry_price is None
    assert record.stop_loss is None
    assert record.price_target is None
    assert record.position_pct is None
    assert record.time_horizon is None
    assert record.settlement_days == 20  # 默认


def test_parse_decision_chinese_freetext_underweight():
    # 真实链路形状：DeepSeek thinking 模式结构化输出降级后的中文自由文本
    pm = "**最终交易决策：600519 贵州茅台**\n\n**最终评级：减持（Underweight）**\n\n维持减持评级。"
    trader = "# 600519 贵州茅台 —— 交易执行提案\n\n**研究决议评级：减持（Underweight）**"

    record = parse_decision_from_state(make_state(pm, trader), fallback_rating="Hold")

    assert record.rating == "Underweight"
    # 中文自由文本无 Action/Entry Price 行，action 由下游按 rating 推导
    assert record.action is None
    assert record.entry_price is None


def test_parse_decision_freetext_degrades_to_fallback_rating():
    record = parse_decision_from_state(
        make_state("自由文本，评级缺失", "自由文本"), fallback_rating="Sell"
    )

    assert record.rating == "Sell"
    assert record.action is None
    assert record.entry_price is None
    assert record.settlement_days == 20


def test_parse_decision_empty_state_uses_fallback():
    record = parse_decision_from_state({}, fallback_rating="Overweight")

    assert record.rating == "Overweight"
    assert record.action is None


def test_parse_action_falls_back_to_final_proposal_line():
    trader = "**Reasoning**: 头部缺失，但结尾在。\n\nFINAL TRANSACTION PROPOSAL: **SELL**"
    record = parse_decision_from_state(make_state(FULL_PM, trader))

    assert record.action == "Sell"


def test_parse_position_pct_takes_range_minimum():
    trader = FULL_TRADER.replace("10% of portfolio", "5-10% of portfolio")
    record = parse_decision_from_state(make_state(FULL_PM, trader))

    assert record.position_pct == 0.05


def test_parse_settlement_days_units():
    assert parse_settlement_days("2 weeks") == 10
    assert parse_settlement_days("10 days") == 10
    assert parse_settlement_days("6 months") == 126
    assert parse_settlement_days("长期持有") == 20
    assert parse_settlement_days(None) == 20


def test_load_state_reads_json_file(tmp_path: Path):
    state_path = tmp_path / "full_states_log_2026-06-03.json"
    state_path.write_text(
        '{"final_trade_decision": "**Rating**: Buy", "trader_investment_decision": ""}',
        encoding="utf-8",
    )

    state = load_state(state_path)

    assert state["final_trade_decision"] == "**Rating**: Buy"


# ---------------------------------------------------------------------------
# 仓库函数
# ---------------------------------------------------------------------------


def test_get_or_create_default_account_is_idempotent(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)

    first = get_or_create_default_account(db_path)
    second = get_or_create_default_account(db_path)

    assert first["id"] == second["id"]
    assert first["cash"] == INITIAL_CASH
    assert first["initial_cash"] == INITIAL_CASH
    assert first["status"] == "active"


def test_create_decision_and_query_by_report(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    report = upsert_report(
        db_path,
        ticker="300750",
        trade_date="2026-06-03",
        signal="Buy",
        summary="摘要",
        state_path="/tmp/state.json",
    )

    record = DecisionRecord(
        rating="Buy",
        action="Buy",
        entry_price=230.5,
        stop_loss=215.0,
        price_target=245.5,
        position_pct=0.10,
        time_horizon="3-6 months",
        settlement_days=63,
    )
    decision = create_decision(
        db_path, report_id=report["id"], ticker="300750", trade_date="2026-06-03", record=record
    )

    assert decision["status"] == "draft"
    assert decision["rating"] == "Buy"
    assert decision["settlement_days"] == 63

    fetched = get_decision_by_report(db_path, report["id"])
    assert fetched["id"] == decision["id"]
    assert fetched["position_pct"] == 0.10
