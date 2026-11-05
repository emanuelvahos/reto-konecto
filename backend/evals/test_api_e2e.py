import os

import jwt
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
EMAIL = "engineer@konecto.io"
PASSWORD = "Konecto2026!"


def _login() -> dict:
    resp = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_login_returns_valid_jwt_and_rejects_bad_password():
    data = _login()
    assert data["token"] == data["access_token"]
    assert data["user"]["email"] == EMAIL

    secret = os.getenv("JWT_SECRET_KEY", "demo-only-change-me")
    claims = jwt.decode(data["token"], secret, algorithms=[os.getenv("JWT_ALGORITHM", "HS256")])
    assert claims["email"] == EMAIL
    assert claims["sub"] == data["user"]["id"]

    bad = client.post("/api/auth/login", json={"email": EMAIL, "password": "WrongPassword"})
    assert bad.status_code == 401

    # Un token inválido debe rechazarse
    r = client.get("/api/sessions", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_multiturn_conversation_coreference_and_persistence():
    # Turno 1: sin session_id -> crea sesión
    t1 = client.post(
        "/api/conversation",
        json={"query": "Give me the technical specs for part number 763B00-11300000/A."},
    )
    assert t1.status_code == 200, t1.text
    d1 = t1.json()
    session_id = d1["session_id"]
    assert session_id
    assert "500" in d1["answer"], d1["answer"]  # On/Off Nm
    assert "380" in d1["answer"], d1["answer"]  # Modulating Nm
    assert len(d1["ui_payload"]["actuators"]) >= 1
    assert d1["ui_payload"]["display_type"] != "TEXT_ONLY"
    assert len(d1["debug_trace"]["tool_calls"]) >= 1
    assert d1["debug_trace"]["model_used"]
    assert "763B00-11300000/A" in d1["debug_trace"]["active_context_part_numbers"]

    # Turno 2: mismo session_id, SIN repetir el part number (correferencia)
    t2 = client.post(
        "/api/conversation",
        json={
            "session_id": session_id,
            "query": "And how much motor power in Watts does it draw, and what is its FLA at 60Hz?",
        },
    )
    assert t2.status_code == 200, t2.text
    d2 = t2.json()
    assert d2["session_id"] == session_id
    assert "90" in d2["answer"], d2["answer"]
    assert "4.8" in d2["answer"], d2["answer"]  # FLA 60 Hz (PDF: 60 Hz | 50 Hz)

    # Persistencia: historial completo en PostgreSQL
    hist = client.get(f"/api/sessions/{session_id}/messages")
    assert hist.status_code == 200
    h = hist.json()
    assert [m["role"] for m in h["messages"]] == ["user", "assistant", "user", "assistant"]
    assert "763B00-11300000/A" in h["active_part_numbers"]
    assert h["messages"][1]["ui_payload"]["actuators"]
    assert h["messages"][1]["debug_trace"]["tool_calls"]

    # La sesión aparece en el listado y se puede borrar
    sessions = client.get("/api/sessions").json()
    assert any(s["session_id"] == session_id and s["message_count"] == 4 for s in sessions)
    assert client.delete(f"/api/sessions/{session_id}").status_code == 200
    assert client.get(f"/api/sessions/{session_id}/messages").status_code == 404
