"""TokenUsageCallback 测试：两种 usage 格式提取、累计、缺省跳过。"""

from __future__ import annotations

from types import SimpleNamespace

from server.services.token_usage import TokenUsageCallback


def _openai_style_response(prompt: int, completion: int, total: int):
    """经典格式：LLMResult.llm_output["token_usage"]。"""
    return SimpleNamespace(
        llm_output={"token_usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
        }},
        generations=[],
    )


def _generation_info_style_response(prompt: int, completion: int):
    """新版格式：generations[*].generation_info["token_usage"]。"""
    gen = SimpleNamespace(
        generation_info={"token_usage": {
            "prompt_tokens": prompt, "completion_tokens": completion
        }},
        message=None,
    )
    return SimpleNamespace(llm_output={}, generations=[[gen]])


def _usage_metadata_style_response(prompt: int, completion: int):
    """新版格式：generations[*].message.usage_metadata。"""
    gen = SimpleNamespace(generation_info={}, message=SimpleNamespace(usage_metadata={
        "input_tokens": prompt, "output_tokens": completion, "total_tokens": prompt + completion
    }))
    return SimpleNamespace(llm_output={}, generations=[[gen]])


def test_accumulates_openai_style_usage():
    tracker = TokenUsageCallback()
    tracker.on_llm_end(_openai_style_response(100, 40, 140))
    tracker.on_llm_end(_openai_style_response(10, 5, 15))
    assert tracker.snapshot() == {
        "calls": 2, "prompt_tokens": 110, "completion_tokens": 45, "total_tokens": 155,
    }


def test_reads_generation_info_fallback():
    tracker = TokenUsageCallback()
    tracker.on_llm_end(_generation_info_style_response(100, 40))
    snap = tracker.snapshot()
    assert snap["calls"] == 1
    assert snap["total_tokens"] == 140  # total 缺省 = prompt + completion


def test_reads_usage_metadata_fallback():
    tracker = TokenUsageCallback()
    tracker.on_llm_end(_usage_metadata_style_response(30, 20))
    assert tracker.snapshot()["total_tokens"] == 50


def test_skips_response_without_usage():
    tracker = TokenUsageCallback()
    tracker.on_llm_end(SimpleNamespace(llm_output={}, generations=[]))
    tracker.on_llm_end(SimpleNamespace(llm_output=None, generations=None))
    assert tracker.snapshot() == {
        "calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
    }


def test_snapshot_is_a_copy():
    tracker = TokenUsageCallback()
    tracker.on_llm_end(_openai_style_response(1, 1, 2))
    snap = tracker.snapshot()
    snap["total_tokens"] = 999
    assert tracker.snapshot()["total_tokens"] == 2
