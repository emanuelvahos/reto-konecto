import json
import uuid
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.database import get_db_cursor
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
    description="Agentic Backend with LangChain/LangGraph, PostgreSQL + pgvector, and X-Ray Debug Telemetry.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/health")
def health_check():
    with get_db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS count FROM actuators;")
        act_count = cur.fetchone()["count"]
    return {"status": "ok", "actuators_loaded": act_count}


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


# =====================================================================
# 2. CORE CONVERSATION ENDPOINT (SECTION 4 API CONTRACT)
# =====================================================================
@app.post("/api/conversation", response_model=ConversationResponse)
def conversation_endpoint(
    req: ConversationRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
):
    user_id = current_user["id"] if current_user else None
    requested_sid = req.session_id.strip() if req.session_id else None

    history_messages: List[Dict[str, Any]] = []
    active_part_numbers: List[str] = []
    active_filters: Dict[str, Any] = {}

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

    # Ejecutar turno del agente con memoria multi-turno
    try:
        answer, ui_payload, debug_trace, updated_parts, updated_filters = run_agent_turn(
            user_query=req.query,
            history_messages=history_messages,
            active_part_numbers=active_part_numbers,
            active_filters=active_filters,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM agent failed: {type(exc).__name__}: {str(exc)[:200]}",
        ) from exc

    # Persistir mensaje del usuario, respuesta del agente y estado actualizado en PostgreSQL
    with get_db_cursor() as cur:
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
        cur.execute(
            """
            UPDATE chat_sessions
            SET active_part_numbers = %s::jsonb,
                active_filters = %s::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE session_id = %s;
            """,
            (
                json.dumps(updated_parts),
                json.dumps(updated_filters),
                session_id,
            ),
        )

    return ConversationResponse(
        session_id=session_id,
        answer=answer,
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
    with get_db_cursor() as cur:
        if current_user:
            cur.execute(
                """
                SELECT s.session_id, s.title, s.active_part_numbers, s.created_at, s.updated_at,
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
                SELECT s.session_id, s.title, s.active_part_numbers, s.created_at, s.updated_at,
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

