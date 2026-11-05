import json
import re
import time
import uuid
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import load_llm_config
from app.database import ensure_schema, get_db_cursor
from app.auth import authenticate_user, create_access_token, get_optional_current_user
from app.schemas import (
    LoginRequest,
    LoginResponse,
    UserInfo,
    ConversationRequest,
    ConversationResponse,
    SessionSummary,
    SessionHistoryResponse,
    MessageRecord,
)
from app.agent import run_agent_turn

app = FastAPI(
    title="Konecto Series 76 Technical Assistant API",
    version="1.0.0",
    description="Agentic Backend with LangChain/LangGraph, PostgreSQL + pg_trgm, and X-Ray Debug Telemetry.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _request_lang(request: Request) -> str:
    """Idioma del error: locale del cuerpo JSON > texto de la consulta > Accept-Language > inglés."""
    from app.i18n import detect_language

    locale, query = None, ""
    try:
        body = await request.json()
        if isinstance(body, dict):
            locale = body.get("locale") if isinstance(body.get("locale"), str) else None
            query = body.get("query") if isinstance(body.get("query"), str) else ""
    except Exception:  # noqa: BLE001  (cuerpo ausente o no JSON)
        pass
    if locale not in ("es", "en") and not query.strip():
        header = (request.headers.get("accept-language") or "").lower()
        locale = "es" if header.startswith("es") else None
    return detect_language(query, locale, [])


def _http_error(status_code: int, message: str, headers: Optional[Dict[str, str]] = None) -> JSONResponse:
    # `detail` (compatible con FastAPI) y `message` llevan el mismo texto corto y localizado, sin detalles internos
    return JSONResponse(status_code=status_code, content={"detail": message, "message": message}, headers=headers)


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    from app.i18n import render_http_error

    return _http_error(422, render_http_error(422, await _request_lang(request)))


@app.exception_handler(StarletteHTTPException)
async def _http_handler(request: Request, exc: StarletteHTTPException):
    from app.i18n import render_http_error

    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return _http_error(exc.status_code, render_http_error(exc.status_code, await _request_lang(request)), headers)


@app.exception_handler(Exception)
async def _unhandled_handler(request: Request, exc: Exception):
    import logging
    from app.i18n import render_http_error

    logging.getLogger("uvicorn.error").error("Unhandled error on %s %s: %s", request.method, request.url.path, type(exc).__name__)
    return _http_error(500, render_http_error(500, await _request_lang(request)))


def is_valid_uuid(val: Optional[str]) -> bool:
    if not val:
        return False
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False


def generate_session_title(query: str) -> str:
    clean = " ".join(query.strip().split())
    return clean[:60] + ("..." if len(clean) > 60 else "")


def assert_session_access(session_user_id: Any, current_user: Optional[Dict[str, Any]]) -> None:
    """Sesiones con dueño solo son accesibles por ese usuario; las anónimas (user_id NULL) son públicas."""
    if session_user_id is None:
        return
    if current_user is None or str(session_user_id) != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this session.")


@app.on_event("startup")
def _startup() -> None:
    import logging

    from app.config import llm_status, startup_message

    ensure_schema()
    log = logging.getLogger("uvicorn.error")
    st = llm_status()
    (log.info if st["configured"] else log.warning)(startup_message(st))
    for note in st["notes"]:
        log.info("Nota: %s", note)


@app.get("/health")
def health_check():
    with get_db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS count FROM actuators;")
        act_count = cur.fetchone()["count"]
    cfg = load_llm_config()
    return {"status": "ok", "actuators_loaded": act_count, "llm_provider": cfg.provider, "llm_model": cfg.chat_model,
            "llm_configured": bool(cfg.api_key.strip())}


# =====================================================================
# 1. AUTH ENDPOINT (OPTIONAL FEATURE SECTION 7)
# =====================================================================
@app.post("/api/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    user = authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    token = create_access_token(user)
    return LoginResponse(
        token=token,
        access_token=token,
        user=UserInfo(**user),
    )


def _controlled_error(req: ConversationRequest, session_id: Optional[str], t0: float, detail: str) -> ConversationResponse:
    """Fallo interno (base de datos, agente): respuesta 200 con texto neutro; el detalle técnico solo va a debug_trace.error."""
    from app.i18n import detect_language, render_alert, render_alert_message

    lang = detect_language(req.query, req.locale, [])
    msg = render_alert_message("SERVICE_UNAVAILABLE", {}, lang)
    return ConversationResponse(
        schema_version=2,
        session_id=session_id or str(uuid.uuid4()),
        answer=msg,
        intent="error",
        verification={"status": "fallback_template", "numbers_checked": 0, "ungrounded": []},
        ui_payload={
            "display_type": "EDGE_CASE_ALERT",
            "actuators": [],
            "engineering_warnings": [msg],
            "alerts": [render_alert({"code": "SERVICE_UNAVAILABLE", "params": {}}, lang)],
        },
        debug_trace={"model_used": "", "total_latency_ms": round((time.perf_counter() - t0) * 1000, 2), "language": lang, "error": detail},
    )


# =====================================================================
# 2. CORE CONVERSATION ENDPOINT (SECTION 4 API CONTRACT)
# =====================================================================
@app.post("/api/conversation", response_model=ConversationResponse)
def conversation_endpoint(
    req: ConversationRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
):
    request_t0 = time.perf_counter()
    req.query = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", req.query) or " "   # PostgreSQL no admite NUL
    try:
        ensure_schema()
    except Exception as exc:  # noqa: BLE001  (base de datos caída)
        return _controlled_error(req, None, request_t0, f"{type(exc).__name__}: {str(exc)[:200]}")
    user_id = current_user["id"] if current_user else None
    requested_sid = req.session_id.strip() if req.session_id else None

    history_messages: List[Dict[str, Any]] = []
    active_part_numbers: List[str] = []
    active_filters: Dict[str, Any] = {}

    history_t0 = time.perf_counter()
    try:
        with get_db_cursor() as cur:
            if requested_sid and is_valid_uuid(requested_sid):
                cur.execute(
                    "SELECT session_id, user_id, title, active_part_numbers, active_filters FROM chat_sessions WHERE session_id = %s;",
                    (requested_sid,),
                )
                session_row = cur.fetchone()

                if session_row:
                    # Si la sesión pertenece a otro usuario autenticado distinto, impedir acceso cruzado
                    assert_session_access(session_row["user_id"], current_user)
                    session_id = str(session_row["session_id"])
                    active_part_numbers = session_row["active_part_numbers"] or []
                    active_filters = session_row["active_filters"] or {}

                    cur.execute(
                        """
                        SELECT role, content
                        FROM chat_messages
                        WHERE session_id = %s
                        ORDER BY created_at ASC, id ASC;
                        """,
                        (session_id,),
                    )
                    history_messages = cur.fetchall()
                else:
                    # Si el cliente envió un UUID nuevo que aún no existe en la BD, lo creamos con ese UUID
                    session_id = requested_sid
                    cur.execute(
                        """
                        INSERT INTO chat_sessions (session_id, user_id, title)
                        VALUES (%s, %s, %s);
                        """,
                        (session_id, user_id, generate_session_title(req.query)),
                    )
            else:
                # Crear nueva conversación con nuevo UUID generado
                session_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO chat_sessions (session_id, user_id, title)
                    VALUES (%s, %s, %s);
                    """,
                    (session_id, user_id, generate_session_title(req.query)),
                )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        return _controlled_error(req, requested_sid if is_valid_uuid(requested_sid) else None, request_t0, f"{type(exc).__name__}: {str(exc)[:200]}")

    history_load_ms = (time.perf_counter() - history_t0) * 1000

    # Ejecutar turno del agente con memoria multi-turno
    try:
        answer, ui_payload, debug_trace, updated_parts, updated_filters, meta = run_agent_turn(
            user_query=req.query,
            history_messages=history_messages,
            active_part_numbers=active_part_numbers,
            active_filters=active_filters,
            locale=req.locale,
            request_t0=request_t0,
            history_load_ms=history_load_ms,
        )
    except Exception as exc:  # noqa: BLE001
        return _controlled_error(req, session_id, request_t0, f"{type(exc).__name__}: {str(exc)[:200]}")

    # Persistir mensaje del usuario, respuesta del agente y estado actualizado en PostgreSQL
    try:
        with get_db_cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET active_part_numbers = %s::jsonb,
                    active_filters = %s::jsonb,
                    short_title = COALESCE(%s, short_title),
                    cost_usd_total = cost_usd_total + %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = %s
                RETURNING cost_usd_total;
                """,
                (
                    json.dumps(updated_parts),
                    json.dumps(updated_filters),
                    meta["short_title"],
                    meta["cost_usd"],
                    session_id,
                ),
            )
            debug_trace["session_cost_usd"] = float(cur.fetchone()["cost_usd_total"])
            cur.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, ui_payload, debug_trace)
                VALUES (%s, 'user', %s, '{}'::jsonb, '{}'::jsonb);
                """,
                (session_id, req.query),
            )
            cur.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, ui_payload, debug_trace)
                VALUES (%s, 'assistant', %s, %s::jsonb, %s::jsonb);
                """,
                (
                    session_id,
                    answer,
                    json.dumps(ui_payload, default=str),
                    json.dumps(debug_trace, default=str),
                ),
            )

    except Exception as exc:  # noqa: BLE001  (la respuesta ya está lista: no se pierde por un fallo al guardar)
        debug_trace["error"] = f"persistence failed: {type(exc).__name__}: {str(exc)[:160]}"

    return ConversationResponse(
        schema_version=2,
        session_id=session_id,
        answer=answer,
        intent=meta["intent"],
        verification=meta["verification"],
        ui_payload=ui_payload,
        debug_trace=debug_trace,
    )


# =====================================================================
# 3. SESSIONS LIST & HISTORY ENDPOINTS (FOR MOBILE APP)
# =====================================================================
@app.get("/api/sessions", response_model=List[SessionSummary])
def list_sessions(
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
):
    ensure_schema()
    with get_db_cursor() as cur:
        if current_user:
            cur.execute(
                """
                SELECT s.session_id, s.title, s.short_title, s.cost_usd_total, s.active_part_numbers, s.created_at, s.updated_at,
                       COUNT(m.id) AS message_count
                FROM chat_sessions s
                LEFT JOIN chat_messages m ON s.session_id = m.session_id
                WHERE s.user_id = %s
                GROUP BY s.session_id
                ORDER BY s.updated_at DESC;
                """,
                (current_user["id"],),
            )
        else:
            cur.execute(
                """
                SELECT s.session_id, s.title, s.short_title, s.cost_usd_total, s.active_part_numbers, s.created_at, s.updated_at,
                       COUNT(m.id) AS message_count
                FROM chat_sessions s
                LEFT JOIN chat_messages m ON s.session_id = m.session_id
                GROUP BY s.session_id
                ORDER BY s.updated_at DESC;
                """
            )
        rows = cur.fetchall()

    return [
        SessionSummary(
            session_id=str(r["session_id"]),
            title=r["title"],
            active_part_numbers=r["active_part_numbers"] or [],
            message_count=r["message_count"],
            short_title=r["short_title"],
            cost_usd_total=float(r["cost_usd_total"] or 0),
            created_at=r["created_at"].isoformat(),
            updated_at=r["updated_at"].isoformat(),
        )
        for r in rows
    ]


@app.get("/api/sessions/{session_id}/messages", response_model=SessionHistoryResponse)
def get_session_messages(
    session_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
):
    if not is_valid_uuid(session_id):
        raise HTTPException(status_code=404, detail="Invalid session_id format.")

    with get_db_cursor() as cur:
        cur.execute(
            "SELECT session_id, user_id, title, active_part_numbers FROM chat_sessions WHERE session_id = %s;",
            (session_id,),
        )
        session_row = cur.fetchone()
        if not session_row:
            raise HTTPException(status_code=404, detail="Conversation session not found.")

        assert_session_access(session_row["user_id"], current_user)

        cur.execute(
            """
            SELECT id, role, content, ui_payload, debug_trace, created_at
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY created_at ASC, id ASC;
            """,
            (session_id,),
        )
        msgs = cur.fetchall()

    return SessionHistoryResponse(
        session_id=str(session_row["session_id"]),
        title=session_row["title"],
        active_part_numbers=session_row["active_part_numbers"] or [],
        messages=[
            MessageRecord(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                ui_payload=m["ui_payload"],
                debug_trace=m["debug_trace"],
                created_at=m["created_at"].isoformat(),
            )
            for m in msgs
        ],
    )


@app.delete("/api/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
):
    if not is_valid_uuid(session_id):
        raise HTTPException(status_code=404, detail="Invalid session_id.")

    with get_db_cursor() as cur:
        cur.execute("SELECT user_id FROM chat_sessions WHERE session_id = %s;", (session_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found.")
        assert_session_access(row["user_id"], current_user)

        cur.execute("DELETE FROM chat_sessions WHERE session_id = %s;", (session_id,))
    return {"status": "deleted", "session_id": session_id}

