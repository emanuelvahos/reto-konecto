"""Errores HTTP (422/404/401/500): JSON corto y localizado, sin trazas, nombres de campos internos, SQL ni rutas."""
import json

import pytest
from fastapi.testclient import TestClient

import app.main as main

LEAKS = ("Traceback", "File \"", "RuntimeError", "psycopg", "SELECT ", "FROM ", "loc", "msg", "pydantic", "string_type",
         "query", "body", ".py", "\\", "/app/", "field required", "Field required", "Not Found")


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app, raise_server_exceptions=False) as c:
        yield c


def assert_clean(r, status, lang_marker):
    assert r.status_code == status
    body = r.json()
    assert set(body) == {"detail", "message"} and body["detail"] == body["message"]
    assert isinstance(body["detail"], str) and 0 < len(body["detail"].split()) <= 20
    assert lang_marker in body["detail"]
    for leak in LEAKS:
        assert leak not in r.text, leak


def test_422_missing_query_spanish_and_english(client):
    assert_clean(client.post("/api/conversation", json={"locale": "es"}), 422, "solicitud")
    assert_clean(client.post("/api/conversation", json={"locale": "en"}), 422, "request")


def test_422_invalid_locale_and_types_and_bad_json(client):
    assert_clean(client.post("/api/conversation", json={"query": "necesito el torque del actuador de 500 Nm", "locale": "fr"}), 422, "solicitud")
    assert_clean(client.post("/api/conversation", json={"query": 123}), 422, "request")
    r = client.post("/api/conversation", content="{not json", headers={"Content-Type": "application/json", "Accept-Language": "es-CO"})
    assert_clean(r, 422, "solicitud")


def test_422_login_body(client):
    assert_clean(client.post("/api/auth/login", json={"email": "x"}, headers={"Accept-Language": "es"}), 422, "solicitud")


def test_404_unknown_route_and_session(client):
    assert_clean(client.get("/api/nope", headers={"Accept-Language": "es"}), 404, "No se encontró")
    assert_clean(client.get("/api/nope"), 404, "Not found")
    assert_clean(client.get("/api/sessions/not-a-uuid/messages"), 404, "Not found")


def test_405_wrong_method(client):
    assert_clean(client.get("/api/conversation"), 405, "not allowed")


def test_401_login_and_bad_token(client):
    r = client.post("/api/auth/login", json={"email": "engineer@konecto.io", "password": "wrong"})
    assert_clean(r, 401, "Authentication")
    r = client.get("/api/sessions", headers={"Authorization": "Bearer not-a-token"})
    assert_clean(r, 401, "Authentication")
    assert r.headers.get("www-authenticate") == "Bearer"


def test_500_internal_failure_hides_details(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("SELECT secret FROM users at /app/app/database.py line 12")

    monkeypatch.setattr(main, "get_db_cursor", boom)
    r = client.get("/health", headers={"Accept-Language": "es"})
    assert_clean(r, 500, "Ocurrió un problema")
    assert "secret" not in r.text and "users" not in r.text
    assert_clean(client.get("/health"), 500, "went wrong")
