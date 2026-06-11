from alphamind.default_config import DEFAULT_CONFIG
from server.core.llm_config import build_research_config


def test_research_config_uses_default_config_without_provider(monkeypatch):
    monkeypatch.delenv("ALPHAMIND_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ALPHAMIND_DEEP_LLM", raising=False)
    monkeypatch.delenv("ALPHAMIND_QUICK_LLM", raising=False)
    monkeypatch.delenv("ALPHAMIND_LLM_BACKEND_URL", raising=False)

    config = build_research_config()

    assert config["llm_provider"] == DEFAULT_CONFIG["llm_provider"]
    assert config["deep_think_llm"] == DEFAULT_CONFIG["deep_think_llm"]
    assert config["quick_think_llm"] == DEFAULT_CONFIG["quick_think_llm"]
    assert config["data_vendors"] == DEFAULT_CONFIG["data_vendors"]
    assert config is not DEFAULT_CONFIG
    assert config["data_vendors"] is not DEFAULT_CONFIG["data_vendors"]


def test_research_config_applies_deepseek_provider_preset(monkeypatch):
    monkeypatch.setenv("ALPHAMIND_LLM_PROVIDER", "deepseek")
    monkeypatch.delenv("ALPHAMIND_DEEP_LLM", raising=False)
    monkeypatch.delenv("ALPHAMIND_QUICK_LLM", raising=False)

    config = build_research_config()

    assert config["llm_provider"] == "deepseek"
    assert config["deep_think_llm"] == "deepseek-v4-pro"
    assert config["quick_think_llm"] == "deepseek-v4-flash"


def test_research_config_allows_explicit_model_overrides(monkeypatch):
    monkeypatch.setenv("ALPHAMIND_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("ALPHAMIND_DEEP_LLM", "deepseek-v4-flash")
    monkeypatch.setenv("ALPHAMIND_QUICK_LLM", "deepseek-chat")
    monkeypatch.setenv("ALPHAMIND_LLM_BACKEND_URL", "https://example.test/v1")

    config = build_research_config()

    assert config["llm_provider"] == "deepseek"
    assert config["deep_think_llm"] == "deepseek-v4-flash"
    assert config["quick_think_llm"] == "deepseek-chat"
    assert config["backend_url"] == "https://example.test/v1"


def test_research_config_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("ALPHAMIND_LLM_PROVIDER", "unknown")

    try:
        build_research_config()
    except ValueError as exc:
        assert "Unsupported ALPHAMIND_LLM_PROVIDER" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported provider")
