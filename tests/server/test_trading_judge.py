"""Judge 校验模块（RuleJudge / LLMJudge / judge_calls 落库）的单元测试。"""

from pathlib import Path
from types import SimpleNamespace

from server.db.connection import init_db
from server.db.repositories import upsert_default_identity, upsert_report
from server.db.trading_repositories import (
    create_decision,
    list_judge_calls,
    record_judge_call,
    update_decision,
)
from server.trading.extraction import DecisionRecord
from server.trading.judge import LLMJudge, RuleJudge, VERDICT_BLOCK, VERDICT_PASS, VERDICT_WARN


def record(**overrides) -> DecisionRecord:
    base = dict(
        rating="Buy",
        action="Buy",
        entry_price=230.5,
        stop_loss=215.0,
        price_target=245.5,
        position_pct=0.10,
        time_horizon="3-6 months",
        settlement_days=63,
    )
    base.update(overrides)
    return DecisionRecord(**base)


# ---------------------------------------------------------------------------
# RuleJudge
# ---------------------------------------------------------------------------


def test_rule_judge_passes_consistent_decision():
    result = RuleJudge().evaluate(record())

    assert result.verdict == VERDICT_PASS
    assert result.checks == []
    assert result.latency_ms >= 0


def test_rule_judge_warns_on_direction_conflict():
    result = RuleJudge().evaluate(record(rating="Sell", action="Buy"))

    assert result.verdict == VERDICT_WARN
    assert result.checks[0]["name"] == "direction_conflict"


def test_rule_judge_blocks_when_stop_loss_above_entry():
    result = RuleJudge().evaluate(record(stop_loss=240.0))

    assert result.verdict == VERDICT_BLOCK
    assert result.checks[0]["name"] == "stop_loss_above_entry"


def test_rule_judge_ignores_stop_loss_check_for_sell():
    result = RuleJudge().evaluate(record(rating="Sell", action="Sell"))

    assert result.verdict == VERDICT_PASS


def test_rule_judge_warns_on_position_over_limit():
    result = RuleJudge().evaluate(record(position_pct=0.30))

    assert result.verdict == VERDICT_WARN
    assert result.checks[0]["name"] == "position_over_limit"


def test_rule_judge_takes_most_severe_verdict():
    result = RuleJudge().evaluate(record(rating="Sell", action="Buy", stop_loss=240.0))

    assert result.verdict == VERDICT_BLOCK
    assert [c["name"] for c in result.checks] == ["direction_conflict", "stop_loss_above_entry"]


def test_rule_judge_tolerates_missing_action():
    result = RuleJudge().evaluate(record(action=None))

    assert result.verdict == VERDICT_PASS


# ---------------------------------------------------------------------------
# LLMJudge
# ---------------------------------------------------------------------------


class FakeLLM:
    def __init__(self, content: str):
        self.content = content
        self.prompts: list[str] = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return SimpleNamespace(content=self.content)


def test_llm_judge_parses_json_verdict():
    llm = FakeLLM('{"verdict": "pass", "reason": "决策自洽"}')
    result = LLMJudge(llm, provider="deepseek").evaluate(record())

    assert result.verdict == VERDICT_PASS
    assert result.provider == "deepseek"
    assert result.checks[0]["message"] == "决策自洽"
    assert result.latency_ms >= 0
    assert "评级: Buy" in llm.prompts[0]


def test_llm_judge_parses_keyword_fallback():
    result = LLMJudge(FakeLLM("我认为应该 warn，仓位偏重")).evaluate(record())

    assert result.verdict == VERDICT_WARN


def test_llm_judge_degrades_to_warn_on_unparseable_output():
    result = LLMJudge(FakeLLM("完全无关的输出")).evaluate(record())

    assert result.verdict == VERDICT_WARN
    assert "无法解析" in result.checks[0]["message"]


def test_llm_judge_degrades_to_warn_on_llm_failure():
    class BrokenLLM:
        def invoke(self, prompt):
            raise RuntimeError("API 超时")

    result = LLMJudge(BrokenLLM()).evaluate(record())

    assert result.verdict == VERDICT_WARN
    assert "LLM 调用失败" in result.checks[0]["message"]


def test_llm_judge_includes_pm_decision_context():
    llm = FakeLLM('{"verdict": "pass", "reason": "ok"}')
    LLMJudge(llm).evaluate(record(), context={"pm_decision": "**Rating**: Buy"})

    assert "**Rating**: Buy" in llm.prompts[0]


# ---------------------------------------------------------------------------
# judge_calls 落库
# ---------------------------------------------------------------------------


def make_decision_row(db_path: Path) -> str:
    report = upsert_report(
        db_path,
        ticker="300750",
        trade_date="2026-06-03",
        signal="Buy",
        summary="摘要",
        state_path="/tmp/state.json",
    )
    decision = create_decision(
        db_path,
        report_id=report["id"],
        ticker="300750",
        trade_date="2026-06-03",
        record=record(),
    )
    return decision["id"]


def test_record_and_list_judge_calls(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    decision_id = make_decision_row(db_path)

    saved = record_judge_call(
        db_path,
        decision_id,
        judge_name="rule",
        verdict=VERDICT_PASS,
        latency_ms=1,
        detail={"verdict": "pass", "checks": []},
    )
    record_judge_call(
        db_path,
        decision_id,
        judge_name="llm",
        verdict=VERDICT_WARN,
        latency_ms=800,
        detail={"provider": "deepseek", "verdict": "warn"},
    )

    calls = list_judge_calls(db_path, decision_id)
    assert [c["judge_name"] for c in calls] == ["rule", "llm"]
    assert calls[0]["detail_json"] == {"verdict": "pass", "checks": []}
    assert calls[1]["detail_json"]["provider"] == "deepseek"
    assert saved["verdict"] == VERDICT_PASS


def test_update_decision_status_and_judge_json(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    upsert_default_identity(db_path)
    decision_id = make_decision_row(db_path)

    updated = update_decision(
        db_path,
        decision_id,
        status="executable",
        judge_json='{"verdict": "pass"}',
    )

    assert updated["status"] == "executable"
    assert updated["judge_json"] == '{"verdict": "pass"}'
