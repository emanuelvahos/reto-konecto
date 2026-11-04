import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import load_llm_config

VARS = ["LLM_PROVIDER", "LLM_BASE_URL", "LLM_CHAT_MODEL", "LLM_API_KEY",
        "LLM_BASE_URL_NIM", "LLM_CHAT_MODEL_NIM", "LLM_API_KEY_NIM"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for v in VARS:
        monkeypatch.delenv(v, raising=False)


def test_default_is_openrouter():
    c = load_llm_config()
    assert c.provider == "openrouter" and "openrouter.ai" in c.base_url and c.chat_model == "openai/gpt-4o-mini"


def test_nim_profile_uses_its_own_key_and_vars(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nim")
    monkeypatch.setenv("LLM_API_KEY", "or-key")
    monkeypatch.setenv("LLM_API_KEY_NIM", "nim-key")
    c = load_llm_config()
    assert c.provider == "nim" and c.api_key == "nim-key" and "nvidia.com" in c.base_url
    assert "nim-key" not in repr(c)


def test_legacy_vars_still_override_openrouter_profile(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1/")
    monkeypatch.setenv("LLM_CHAT_MODEL", "x/y")
    c = load_llm_config()
    assert (c.base_url, c.chat_model) == ("https://example.test/v1", "x/y")


def test_invalid_provider_rejected(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "foo")
    with pytest.raises(ValueError):
        load_llm_config()
