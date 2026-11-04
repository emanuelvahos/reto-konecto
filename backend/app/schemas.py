from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# --- AUTH SCHEMAS ---
class LoginRequest(BaseModel):
    email: str = Field(..., examples=["engineer@konecto.io"])
    password: str = Field(..., examples=["Konecto2026!"])


class UserInfo(BaseModel):
    id: str
    email: str
    full_name: str
    role: str


class LoginResponse(BaseModel):
    token: str
    access_token: str  # Alias por compatibilidad estándar OAuth2/Bearer
    token_type: str = "bearer"
    user: UserInfo


# --- CONVERSATION CONTRACT SCHEMAS ---
class ConversationRequest(BaseModel):
    session_id: Optional[str] = Field(
        None,
        description="Optional conversation UUID. If omitted or empty, a new session is created.",
    )
    query: str = Field(..., min_length=1, description="User's technical question or requirement.")
    locale: Optional[Literal["es", "en"]] = None
    input_mode: Optional[Literal["text", "voice"]] = None


class ToolCallTrace(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    sql_executed: Optional[str] = None
    raw_output: Any
    execution_time_ms: float


class TraceStep(BaseModel):
    name: str
    start_ms: float
    duration_ms: float


class DebugTracePayload(BaseModel):
    model_used: str
    total_latency_ms: float
    token_usage: Dict[str, Any] = Field(default_factory=dict)
    active_context_part_numbers: List[str] = Field(default_factory=list)
    tool_calls: List[ToolCallTrace] = Field(default_factory=list)
    steps: List[TraceStep] = Field(default_factory=list)
    cost_usd_estimate: float = 0.0
    provider: str = ""
    session_cost_usd: float = 0.0
    language: str = ""


class UIAlert(BaseModel):
    code: str
    severity: str
    message: str


class RankedActuator(BaseModel):
    part_number: str
    score: float
    why: List[str] = Field(default_factory=list)
    why_not: List[str] = Field(default_factory=list)


class RecommendationPayload(BaseModel):
    ranking: List[RankedActuator] = Field(default_factory=list)
    hard_constraints: List[str] = Field(default_factory=list)
    relaxed_constraints: List[str] = Field(default_factory=list)


class ClarificationOption(BaseModel):
    label: str
    value: str


class ClarificationPayload(BaseModel):
    question: str
    options: List[ClarificationOption] = Field(default_factory=list)


class UIPayload(BaseModel):
    display_type: str = Field(
        "TEXT_ONLY",
        description=(
            "SINGLE_SPEC_CARD | COMPARISON_TABLE | EDGE_CASE_ALERT | TEXT_ONLY | "
            "RECOMMENDATION_LIST | CLARIFICATION"
        ),
    )
    actuators: List[Dict[str, Any]] = Field(default_factory=list)
    engineering_warnings: List[str] = Field(default_factory=list)
    alerts: List[UIAlert] = Field(default_factory=list)
    recommendation: Optional[RecommendationPayload] = None
    clarification: Optional[ClarificationPayload] = None


class Verification(BaseModel):
    status: Literal["verified", "fallback_template", "unverified"] = "unverified"
    numbers_checked: int = 0
    ungrounded: List[str] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    schema_version: int = 2
    intent: Literal["lookup", "recommend", "knowledge", "clarify", "error"] = "lookup"
    verification: Verification = Field(default_factory=Verification)
    session_id: str
    answer: str
    ui_payload: UIPayload
    debug_trace: DebugTracePayload


# --- SESSION MANAGEMENT SCHEMAS ---
class SessionSummary(BaseModel):
    session_id: str
    title: str
    active_part_numbers: List[str] = Field(default_factory=list)
    message_count: int = 0
    short_title: Optional[str] = None
    cost_usd_total: float = 0.0
    created_at: str
    updated_at: str


class MessageRecord(BaseModel):
    id: int
    role: str
    content: str
    ui_payload: Optional[Dict[str, Any]] = None
    debug_trace: Optional[Dict[str, Any]] = None
    created_at: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    title: str
    active_part_numbers: List[str]
    messages: List[MessageRecord]