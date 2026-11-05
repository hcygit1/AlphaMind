"""Token 用量统计：LangChain callback 累计每次 LLM 调用的 usage。

兼容两种返回格式：
- OpenAI/DeepSeek 经典格式：LLMResult.llm_output["token_usage"]
- LangChain 新版格式：generations[*].generation_info["token_usage"] / usage_metadata
"""

from __future__ import annotations

import threading
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler


class TokenUsageCallback(BaseCallbackHandler):
    """线程安全累计 LLM token 用量；snapshot() 返回汇总 dict。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        usage = self._extract_usage(response)
        if not usage:
            return
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        total = int(usage.get("total_tokens") or (prompt + completion))
        with self._lock:
            self.calls += 1
            self.prompt_tokens += prompt
            self.completion_tokens += completion
            self.total_tokens += total

    @staticmethod
    def _extract_usage(response: Any) -> dict[str, Any] | None:
        # 1) 经典格式
        llm_output = getattr(response, "llm_output", None) or {}
        usage = llm_output.get("token_usage") or llm_output.get("usage")
        if usage:
            return usage
        # 2) 新版格式：token_usage 或 usage_metadata 挂在 generation 上
        for gen_list in getattr(response, "generations", []) or []:
            for gen in gen_list:
                info = getattr(gen, "generation_info", None) or {}
                usage = info.get("token_usage") or info.get("usage_metadata")
                if usage:
                    return usage
                message = getattr(gen, "message", None)
                usage = getattr(message, "usage_metadata", None)
                if usage:
                    return usage
        return None

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "calls": self.calls,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            }
