"""Tests for the shared rating heuristic and the SignalProcessor adapter.

The Portfolio Manager produces a typed PortfolioDecision via structured
output and renders it to markdown that always contains a ``**Rating**: X``
header.  The deterministic heuristic in ``alphamind.agents.utils.rating``
is therefore sufficient to extract the rating downstream — no second LLM
call is needed — and SignalProcessor is now a thin adapter that delegates
to it.
"""

import pytest

from alphamind.agents.utils.rating import RATINGS_5_TIER, parse_rating
from alphamind.graph.signal_processing import SignalProcessor


# ---------------------------------------------------------------------------
# Heuristic parser
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseRating:
    def test_explicit_label_buy(self):
        assert parse_rating("Rating: Buy\nReasoning here.") == "Buy"

    def test_explicit_label_overweight(self):
        assert parse_rating("Rating: Overweight\nDetails.") == "Overweight"

    def test_explicit_label_with_markdown_bold_value(self):
        # Regression: Rating: **Sell** — markdown around the value.
        assert parse_rating("Rating: **Sell**\nExit immediately.") == "Sell"

    def test_explicit_label_with_markdown_bold_label(self):
        assert parse_rating("**Rating**: Underweight\nTrim exposure.") == "Underweight"

    def test_rendered_pm_markdown_shape(self):
        # The exact shape produced by render_pm_decision must always parse.
        text = (
            "**Rating**: Buy\n\n"
            "**Executive Summary**: Enter at $189-192, 6% portfolio cap.\n\n"
            "**Investment Thesis**: AI capex cycle intact; institutional flows constructive."
        )
        assert parse_rating(text) == "Buy"

    def test_explicit_label_wins_over_prose_with_markdown(self):
        text = (
            "The buy thesis is weakened by guidance.\n"
            "Rating: **Sell**\n"
            "Exit before earnings."
        )
        assert parse_rating(text) == "Sell"

    def test_no_rating_returns_default(self):
        assert parse_rating("No clear directional signal at this time.") == "Hold"

    def test_no_rating_custom_default(self):
        assert parse_rating("Plain prose.", default="Underweight") == "Underweight"

    def test_all_five_tiers_recognised(self):
        for r in RATINGS_5_TIER:
            assert parse_rating(f"Rating: {r}") == r

    def test_chinese_label_with_chinese_alias(self):
        # 真实链路形状：DeepSeek 中文输出「**最终评级：减持（Underweight）**」
        assert parse_rating("**最终评级：减持（Underweight）**") == "Underweight"

    def test_chinese_label_plain(self):
        assert parse_rating("评级：买入\n\n执行摘要：分批建仓。") == "Buy"

    def test_chinese_alias_variants(self):
        assert parse_rating("评级：增持") == "Overweight"
        assert parse_rating("评级：超配") == "Overweight"
        assert parse_rating("评级：中性") == "Hold"
        assert parse_rating("评级：低配") == "Underweight"
        assert parse_rating("评级：卖出") == "Sell"
        assert parse_rating("评级：清仓") == "Sell"

    def test_english_word_wrapped_in_chinese_parens(self):
        # 第二趟兜底：括号剥离后应识别英文 5-tier 词
        assert parse_rating("结论（Sell）明确，执行离场。") == "Sell"

    def test_chinese_unrelated_label_does_not_match(self):
        # 「评级」后接非评级词时应继续找，不误报
        assert parse_rating("评级调整触发：观察名单") == "Hold"


# ---------------------------------------------------------------------------
# SignalProcessor: thin adapter over the heuristic
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSignalProcessor:
    def test_returns_rating_from_pm_markdown(self):
        sp = SignalProcessor()
        md = "**Rating**: Overweight\n\n**Executive Summary**: Build gradually."
        assert sp.process_signal(md) == "Overweight"

    def test_makes_no_llm_calls(self):
        """SignalProcessor must not invoke the LLM it was constructed with —
        the rating is parseable from the rendered PM markdown directly."""
        from unittest.mock import MagicMock

        llm = MagicMock()
        sp = SignalProcessor(llm)
        sp.process_signal("Rating: Buy\nDetails.")
        llm.invoke.assert_not_called()
        llm.with_structured_output.assert_not_called()

    def test_default_when_no_rating_present(self):
        sp = SignalProcessor()
        assert sp.process_signal("Plain prose without a recommendation.") == "Hold"
