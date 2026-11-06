import sys
from pathlib import Path

# Permite `from app...` al correr pytest desde la raíz del repo o desde backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch):
    """Los reintentos del agente esperan RETRY_BASE_S * 2**n; en pruebas no se duerme."""
    import app.agent as agent

    monkeypatch.setattr(agent, "RETRY_BASE_S", 0.0)


@pytest.fixture(autouse=True)
def _router_off_by_default(monkeypatch):
    """Las pruebas del pipeline simulan al LLM decidiendo las herramientas; el router se prueba aparte (test_router.py)."""
    import app.agent as agent

    monkeypatch.setattr(agent, "ROUTER_ENABLED", False)


class FakeClassifierLLM:
    """LLM falso del clasificador: devuelve texto fijo (o lanza la excepción dada) y registra los mensajes recibidos."""

    def __init__(self, reply):
        self.reply, self.calls, self.messages = reply, 0, []

    def invoke(self, messages):
        from langchain_core.messages import AIMessage

        self.calls += 1
        self.messages = messages
        if isinstance(self.reply, BaseException):
            raise self.reply
        return AIMessage(content=self.reply, usage_metadata={"input_tokens": 300, "output_tokens": 40, "total_tokens": 340})


@pytest.fixture
def fake_classifier(monkeypatch):
    """fake_classifier(reply) instala un clasificador falso (texto JSON o excepción) y devuelve el objeto para inspeccionarlo."""
    import app.agent as agent

    def install(reply):
        fake = FakeClassifierLLM(reply)
        monkeypatch.setattr(agent, "build_llm_for_classifier", lambda: fake)
        return fake

    return install
