"""Persistencia a través de un reinicio REAL del contenedor del backend (opt-in: RUN_LIVE=1; usa Docker y el LLM configurado).

    RUN_LIVE=1 python -m pytest evals/test_robustness_live.py -q
"""
import os
import subprocess
import time

import httpx
import pytest

BASE = os.getenv("LIVE_BASE_URL", "http://localhost:8001")
CONTAINER = os.getenv("LIVE_CONTAINER", "series76_backend")
PN = "764A00-11320000/A"

pytestmark = pytest.mark.skipif(os.getenv("RUN_LIVE") != "1", reason="opt-in: RUN_LIVE=1 (reinicia el contenedor y llama al LLM)")


def _wait_healthy(timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if httpx.get(f"{BASE}/health", timeout=3).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise AssertionError("el backend no volvió a estar sano")


def test_history_and_active_parts_survive_a_backend_restart_mid_session():
    with httpx.Client(base_url=BASE, timeout=60) as c:
        first = c.post("/api/conversation", json={"query": f"¿Qué torque tiene el {PN}?", "locale": "es"}).json()
        sid = first["session_id"]
        assert first["debug_trace"]["active_context_part_numbers"] == [PN]

    subprocess.run(["docker", "restart", CONTAINER], check=True, capture_output=True, timeout=120)
    _wait_healthy()

    with httpx.Client(base_url=BASE, timeout=60) as c:
        hist = c.get(f"/api/sessions/{sid}/messages").json()
        roles = [m["role"] for m in hist["messages"]]
        assert roles == ["user", "assistant"]                                    # el historial sobrevivió
        second = c.post("/api/conversation", json={"query": "¿y su potencia?", "session_id": sid, "locale": "es"}).json()
        assert second["session_id"] == sid
        assert second["debug_trace"]["active_context_part_numbers"] == [PN]       # las partes activas sobrevivieron
        assert [a["base_part_number"] for a in second["ui_payload"]["actuators"]] == [PN]
