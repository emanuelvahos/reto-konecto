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
