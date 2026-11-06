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


def test_no_provider_set_uses_openrouter_and_reads_llm_api_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "or-key")
    monkeypatch.setenv("LLM_API_KEY_NIM", "nim-key")
    c = load_llm_config()
    assert c.provider == "openrouter" and c.api_key == "or-key"


def test_nim_reads_llm_api_key_nim_only(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nim")
    monkeypatch.setenv("LLM_API_KEY", "or-key")
    assert load_llm_config().api_key == ""            # la clave de OpenRouter no se usa con nim
    monkeypatch.setenv("LLM_API_KEY_NIM", "nim-key")
    assert load_llm_config().api_key == "nim-key"


def test_status_missing_key_message_and_flag():
    from app.config import llm_status, startup_message

    st = llm_status()
    assert st["provider"] == "openrouter" and st["configured"] is False and st["notes"] == []
    assert startup_message(st) == ("LLM no configurado: falta LLM_API_KEY para el proveedor openrouter; "
                                   "el servicio responde en modo degradado")


def test_status_with_key_and_other_provider_key_only_notes(monkeypatch):
    from app.config import llm_status, startup_message

    monkeypatch.setenv("LLM_API_KEY", "or-key")
    monkeypatch.setenv("LLM_API_KEY_NIM", "nim-key")
    st = llm_status()
    assert st["provider"] == "openrouter" and st["configured"] is True      # no cambia de proveedor
    assert len(st["notes"]) == 1 and "LLM_API_KEY_NIM" in st["notes"][0] and "nim-key" not in st["notes"][0]
    assert startup_message(st).startswith("LLM configurado")


def test_status_nim_missing_key_names_nim_variable(monkeypatch):
    from app.config import llm_status, startup_message

    monkeypatch.setenv("LLM_PROVIDER", "nim")
    monkeypatch.setenv("LLM_API_KEY", "or-key")
    st = llm_status()
    assert st["configured"] is False and "LLM_API_KEY_NIM" in startup_message(st) and len(st["notes"]) == 1


def test_health_exposes_llm_configured_and_startup_logs(monkeypatch, caplog):
    import logging

    from fastapi.testclient import TestClient

    import app.main as main

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        with TestClient(main.app) as c:
            h = c.get("/health").json()
            assert h["llm_configured"] is False and h["llm_provider"] == "openrouter"
            monkeypatch.setenv("LLM_API_KEY", "or-key")
            h2 = c.get("/health").json()
            assert h2["llm_configured"] is True and "or-key" not in str(h2)
    assert any("LLM no configurado: falta LLM_API_KEY para el proveedor openrouter" in r.getMessage()
               and r.levelno == logging.WARNING for r in caplog.records)
