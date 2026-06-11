"""LLM runtime configuration for the FastAPI workbench."""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

from alphamind.default_config import DEFAULT_CONFIG


LLM_PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "deepseek": {
        "llm_provider": "deepseek",
        "deep_think_llm": "deepseek-v4-pro",
        "quick_think_llm": "deepseek-v4-flash",
    },
    "openai": {
        "llm_provider": "openai",
        "deep_think_llm": "gpt-5.4",
        "quick_think_llm": "gpt-5.4-mini",
    },
    "openrouter": {
        "llm_provider": "openrouter",
        "deep_think_llm": "anthropic/claude-sonnet-4.5",
        "quick_think_llm": "openai/gpt-4.1-mini",
    },
    "qwen": {
        "llm_provider": "qwen",
        "deep_think_llm": "qwen-plus",
        "quick_think_llm": "qwen-turbo",
    },
}


def build_research_config() -> dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)

    provider = os.getenv("ALPHAMIND_LLM_PROVIDER", "").strip().lower()
    if provider:
        preset = LLM_PROVIDER_PRESETS.get(provider)
        if preset is None:
            raise ValueError(f"Unsupported ALPHAMIND_LLM_PROVIDER: {provider}")
        config.update(preset)

    deep_model = os.getenv("ALPHAMIND_DEEP_LLM")
    quick_model = os.getenv("ALPHAMIND_QUICK_LLM")
    backend_url = os.getenv("ALPHAMIND_LLM_BACKEND_URL")

    if deep_model:
        config["deep_think_llm"] = deep_model
    if quick_model:
        config["quick_think_llm"] = quick_model
    if backend_url:
        config["backend_url"] = backend_url

    return config
