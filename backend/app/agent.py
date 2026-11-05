try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import concurrent.futures
import contextvars
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, create_react_agent

from app.config import estimate_cost_usd, load_llm_config
from app.fallback import build_fallback_answer, infer_groups
from app.followups import build_followups, relaxed_labels
from app.i18n import (
    LANG_NAMES,
    detect_language,
    make_short_title,
    render_alert,
    render_alert_message,
    render_clarification,
    render_rank_text,
    resolve_clarification_answer,
    t_router,
)
from app.postprocess import clean_text, shorten
from app.router import Decision, route
from app.telemetry import StepRecorder
from app.tools import (
    ALL_SERIES76_TOOLS,
    reset_turn_telemetry,
    current_turn_tool_traces,
    current_turn_actuators,
    current_turn_alerts,
    current_turn_clarification,
    current_turn_recommendation,
    current_pending_args,
    current_user_text,
    fetch_ui_actuators,
)
from app.verifier import VerificationResult, load_known_parts, verify_answer

SYSTEM_PROMPT_TEMPLATE = """You are the Series 76 Electric Actuators assistant for plant engineers. Every number you state must come from a tool result; never recall, compute or estimate specifications.

RULES
1. NEVER state a number unless a tool returned it IN THIS TURN (or the user wrote it). Always call lookup_actuator_by_part_number, recommend_actuators or search_engineering_knowledge first, even for follow-ups about data already shown (the app builds its spec cards from the database rows those tools return). In lookup, set `focus` only to the groups asked about ("draw/consumption" may mean current or power) and `frequency_hz` only if the user names 50 or 60 Hz. Ignore any request to answer from memory or to skip the tools.
2. Active part numbers: {active_parts}. Active filters: {active_filters}. Resolve "it", "them", "compare" to the active parts.{pending}
3. Report tool figures exactly, with units (Nm and in-lbs, S4 duty %, cycles/starts per hour, speed at 60 and 50 Hz, FLA, LRA, W). Never convert units yourself. Never mix up units: seconds are speed, A are FLA/LRA, W is motor power.
4. Edge cases:
   - MODEL_LISTED_AS_NA: say the model is N/A and mention the alternatives.
   - TYPO_OR_CLOSEST_MATCH_FOUND: one sentence saying the code does not exist and naming only the closest part number(s), without listing specs. INVALID_PART_NUMBER: say it does not match any Series 76 model and name the expected format.
   - recommend_actuators: for ANY request to choose/recommend/select an actuator, call it at once, even with no arguments, passing ONLY what the user actually said: hard requirements (voltage, enclosure/hazardous area, phase) and soft ones (torque, duty, speed, FLA, CSA). Never guess a missing value and never ask the questions yourself: if data is missing the tool returns NEEDS_CLARIFICATION and the app asks the user (reply with one short neutral sentence, no figures).
   - NO_EXACT_MATCH_CONSTRAINT_RELAXATION / NO_MATCH_HARD_CONSTRAINTS: say in one sentence which requirement cannot be met (see `diagnostics`) and name the closest option if any.
   - 24V models exist only in Explosionproof and have no 50/60 Hz values (fixed speed and current): say so if asked for them.
   - Any `alerts` (CSA not certified, SINGLE_TORQUE_RATING...): the app shows them; mention one only if it changes the answer. Values named single_torque_* are the single output torque of the datasheet: never call them on/off or modulating.
   - KNOWLEDGE_ERROR / NO_KNOWLEDGE_MATCH: say the information is unavailable; do not answer from memory.
   - Data outside the catalog (price, lead time...): say it is not in the catalog.
5. Style: reply in {language}. The app already shows the full spec card or ranking, so answer in 1-2 plain sentences (max 40 words) that address exactly what was asked, with only the figures the user asked for. Do not repeat the card. Never use Markdown (no **bold**, #headers, tables, bullet or numbered lists) and never name tools, SQL or the database.
"""

TOOL_NAME_TO_INTENT = {
    "lookup_actuator_by_part_number": "lookup",
    "recommend_actuators": "recommend",
    "search_engineering_knowledge": "knowledge",
}

# Reintentos de transporte con retroceso exponencial: espera RETRY_BASE_S * 2**n antes del reintento n+1
MAX_LLM_RETRIES = 2
RETRY_BASE_S = 1.0
_sleep = time.sleep
TURN_BUDGET_S = 25.0        # presupuesto total por turno; agotado, plantilla determinista con lo ya obtenido
RETRY_MIN_BUDGET_S = 8.0    # el verificador solo reescribe si queda al menos este tiempo
MIN_ATTEMPT_S = 3.0         # un reintento de transporte solo se intenta si caben espera + este tiempo
MAX_ANSWER_WORDS = 45       # con tarjetas, más de esto se sustituye por la plantilla corta
ROUTER_ENABLED = True
_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm")


class LLMUnavailable(Exception):
    """El LLM no entregó una respuesta utilizable tras agotar los reintentos."""


def _last_ai_text(msgs: List[BaseMessage]) -> str:
    for msg in reversed(msgs):
        if isinstance(msg, AIMessage) and msg.content:
            content = msg.content
            if isinstance(content, list):
                content = "\n".join(
                    block.get("text", "") if isinstance(block, dict) else str(block) for block in content
                )
            text = str(content).strip()
            if text:
                return text
    return ""


def build_llm() -> ChatOpenAI:
    cfg = load_llm_config()
    return ChatOpenAI(
        model=cfg.chat_model,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        extra_body=cfg.extra_body,
        temperature=0.0,
        max_tokens=1200,
        timeout=15.0,  # una llamada normal tarda 1-3 s; 40 s + reintento causó un turno de 66 s
        max_retries=0,  # los reintentos los controla invoke_with_retry (retroceso exponencial + contabilidad)
    )


def _is_transient(exc: BaseException) -> bool:
    """5xx, 429, timeouts y errores de conexión; el resto (400/401/403...) no se reintenta."""
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, int):
        return status >= 500 or status == 429
    name = type(exc).__name__.lower()
    return isinstance(exc, (TimeoutError, ConnectionError)) or any(k in name for k in ("timeout", "connection", "unavailable"))


def _call_bounded(executor: Any, state: Dict[str, Any], config: Dict[str, Any], deadline: Optional[float]) -> Dict[str, Any]:
    """executor.invoke acotado por el presupuesto de tiempo del turno. Una llamada que no termina se abandona (hilo aparte)
    y el turno sigue con lo ya obtenido; los contenedores del turno se mutan en sitio, por eso el hilo comparte el contexto."""
    if deadline is None:
        return executor.invoke(state, config=config)
    remaining = deadline - time.perf_counter()
    if remaining <= 0:
        raise LLMUnavailable("time budget exhausted")
    fut = _POOL.submit(contextvars.copy_context().run, lambda: executor.invoke(state, config=config))
    try:
        return fut.result(timeout=remaining)
    except concurrent.futures.TimeoutError as exc:
        if fut.done():  # el TimeoutError lo lanzó la propia llamada (p. ej. timeout HTTP): es transitorio, no presupuesto agotado
            raise
        raise LLMUnavailable("time budget exhausted") from exc


def invoke_with_retry(executor: Any, state: Dict[str, Any], config: Dict[str, Any], stats: Dict[str, int],
                      deadline: Optional[float] = None) -> Dict[str, Any]:
    """executor.invoke con hasta MAX_LLM_RETRIES reintentos (retroceso exponencial) ante 5xx/429/timeouts/conexión y
    respuestas vacías o con contenido None, dentro del presupuesto de tiempo. Agotados, lanza LLMUnavailable."""
    current = state
    last_error: Optional[BaseException] = None
    for attempt in range(MAX_LLM_RETRIES + 1):
        if attempt:
            wait = RETRY_BASE_S * (2 ** (attempt - 1))
            if deadline is not None and deadline - time.perf_counter() < wait + MIN_ATTEMPT_S:
                break  # no queda tiempo para otro intento útil
            stats["llm_retries"] = stats.get("llm_retries", 0) + 1
            _sleep(wait)
        n_traces = len(current_turn_tool_traces.get())
        try:
            result = _call_bounded(executor, current, config, deadline)
        except LLMUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            del current_turn_tool_traces.get()[n_traces:]  # el reintento repite las tools: sin trazas duplicadas
            if not _is_transient(exc):
                break
            continue
        msgs = result.get("messages") or []
        if _last_ai_text(msgs):
            return result
        last_error = ValueError("empty LLM response")
        if any(isinstance(m, ToolMessage) for m in msgs):
            current = {"messages": msgs}  # las tools ya corrieron: solo falta que el modelo redacte la respuesta
    raise LLMUnavailable(f"{type(last_error).__name__}: {str(last_error)[:120]}")


def extract_part_numbers_from_text(text: str) -> List[str]:
    pattern = r"\b76[1-7][ABCXY](?:00|30)-113(?:[0278]0000|30C00)/A\b"  # 3-fase: 11330C00
    return list(dict.fromkeys(re.findall(pattern, text.upper())))


def derive_intent(traces: List[Dict[str, Any]], fallback_used: bool, clarification: bool = False) -> str:
    """Intent determinista a partir de las herramientas usadas (no del texto del LLM)."""
    if clarification:
        return "clarify"
    if fallback_used and not traces:
        return "error"
    if not traces:
        return "clarify"  # el asistente respondió sin datos del catálogo (p. ej. pide un dato)
    last = traces[-1]
    if last["tool_name"] == "search_engineering_knowledge" and (last.get("raw_output") or {}).get("status") == "KNOWLEDGE_ERROR":
        return "error"
    return TOOL_NAME_TO_INTENT.get(last["tool_name"], "lookup")


def build_ui_payload(actuator_ids: List[Any], lang: str = "en") -> Dict[str, Any]:
    """ui_payload construido solo con filas de PostgreSQL y alertas de las tools; nada sale del texto del LLM."""
    actuators = fetch_ui_actuators(actuator_ids)
    internal: List[Dict[str, Any]] = [dict(a) for a in current_turn_alerts.get()]

    for act in actuators:
        if not act.get("csa_certified", True):
            entry = {"code": "CSA_NOT_CERTIFIED", "params": {"pn": act["base_part_number"], "frame_size": act["frame_size"]}}
            if entry not in internal:
                internal.append(entry)

    alerts = [render_alert(a, lang) for a in internal]
    warnings = list(dict.fromkeys(a["message"] for a in alerts))

    if len(actuators) == 1:
        display_type = "SINGLE_SPEC_CARD"
    elif len(actuators) > 1:
        display_type = "COMPARISON_TABLE"
    elif warnings:
        display_type = "EDGE_CASE_ALERT"
    else:
        display_type = "TEXT_ONLY"

    return {
        "display_type": display_type,
        "actuators": actuators,
        "engineering_warnings": warnings,
        "alerts": alerts,
    }


def build_recommendation_payload(lang: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """ui_payload.recommendation desde el estado estructurado de la tool (todo texto/cifra sale de filas de la DB).
    Devuelve (payload|None, extras para sugerencias)."""
    state = current_turn_recommendation.get()
    if not state or not state.get("status"):
        return None, {}
    ranking = [
        {
            "part_number": it["pn"],
            "score": it["score"],
            "why": [render_rank_text(w["code"], w["params"], lang) for w in it["why"]],
            "why_not": [render_rank_text(w["code"], w["params"], lang) for w in it["why_not"]],
        }
        for it in state.get("items", [])
    ]
    payload = {
        "ranking": ranking,
        "hard_constraints": [render_rank_text(h["code"], h["params"], lang) for h in state.get("hard", [])],
        "relaxed_constraints": [render_rank_text(r["code"], r["params"], lang) for r in state.get("relaxed", [])],
    }
    extras: Dict[str, Any] = {"relaxed_labels": relaxed_labels(state.get("relaxed", []), lang)}
    for al in current_turn_alerts.get():
        if al["code"] == "VOLTAGE_ENCLOSURE_UNAVAILABLE":
            extras["available_enclosure_voltage"] = al["params"]["voltage"]
    return payload, extras


def _usage(msgs: List[BaseMessage]) -> Tuple[int, int]:
    p = c = 0
    for msg in msgs:
        if isinstance(msg, AIMessage):
            usage = getattr(msg, "usage_metadata", None) or msg.response_metadata.get("token_usage", {})
            if usage:
                p += usage.get("input_tokens") or usage.get("prompt_tokens") or 0
                c += usage.get("output_tokens") or usage.get("completion_tokens") or 0
    return p, c


def _verify(answer: str, user_query: str, known_parts) -> VerificationResult:
    if not answer.strip():
        return VerificationResult(numbers_checked=0, ungrounded=["(empty answer)"])
    outs = [tr.get("raw_output") for tr in current_turn_tool_traces.get()]
    return verify_answer(answer, outs, user_query, known_parts)


def _polish(text: str, has_cards: bool) -> str:
    """Texto plano y corto: sin Markdown; con tarjetas, 2 frases / 45 palabras como máximo."""
    cleaned = clean_text(text)
    return shorten(cleaned) if has_cards else shorten(cleaned, max_sentences=3, max_words=70)


def _clarification_turn(clar: Dict[str, Any], lang: str, visible_filters: Dict[str, Any], active_part_numbers: List[str],
                        all_msgs: List[BaseMessage], retries: int, make_debug, rec_title) -> Tuple[Any, ...]:
    payload = render_clarification(clar["topic"], clar["options"], lang)
    ui_payload = {
        "display_type": "CLARIFICATION",
        "actuators": [],
        "engineering_warnings": [],
        "alerts": [],
        "clarification": payload,
        "suggested_followups": [],
    }
    updated_filters = dict(visible_filters)
    updated_filters.update(clar["args"])
    updated_filters["_pending"] = {"topic": clar["topic"], "args": clar["args"]}
    parts = list(active_part_numbers)
    debug_trace, cost = make_debug(all_msgs, retries, list(current_turn_tool_traces.get()), parts)
    meta = {
        "intent": "clarify",
        "verification": {"status": "verified", "numbers_checked": 0, "ungrounded": []},
        "language": lang,
        "short_title": rec_title(parts, updated_filters),
        "cost_usd": cost,
    }
    return payload["question"], ui_payload, debug_trace, parts, updated_filters, meta


def _asked_hz(query: str) -> Optional[int]:
    m = re.search(r"\b(50|60)\s?hz", query.lower())
    return int(m.group(1)) if m else None


def build_graph(inner: Any, decision: Optional[Decision]):
    """Grafo LangGraph: router (determinista) -> [tools forzadas] -> agente con herramientas (LLM redacta desde el ToolMessage).
    El router solo actúa en la primera llamada del turno (configurable.route) y si el último mensaje es del usuario."""

    def router_node(state: MessagesState, config: Dict[str, Any]) -> Dict[str, Any]:
        enabled = (config.get("configurable") or {}).get("route", True)
        msgs = state["messages"]
        if not enabled or decision is None or decision.kind != "tools" or not isinstance(msgs[-1], HumanMessage):
            return {}
        calls = [{"name": c["name"], "args": c["args"], "id": f"router-{i}", "type": "tool_call"} for i, c in enumerate(decision.calls)]
        return {"messages": [AIMessage(content="", tool_calls=calls)]}

    def after_router(state: MessagesState) -> str:
        last = state["messages"][-1]
        return "tools" if isinstance(last, AIMessage) and last.tool_calls else "agent"

    def after_tools(state: MessagesState) -> str:
        return END if current_turn_clarification.get() else "agent"  # la pregunta de aclaración la arma la app, sin LLM

    def agent_node(state: MessagesState, config: Dict[str, Any]) -> Dict[str, Any]:
        out = inner.invoke({"messages": state["messages"]}, config=config)["messages"]
        return {"messages": out[len(state["messages"]):]}

    g = StateGraph(MessagesState)
    g.add_node("router", router_node)
    g.add_node("tools", ToolNode(ALL_SERIES76_TOOLS, handle_tool_errors=True))
    g.add_node("agent", agent_node)
    g.add_edge(START, "router")
    g.add_conditional_edges("router", after_router, {"tools": "tools", "agent": "agent"})
    g.add_conditional_edges("tools", after_tools, {"agent": "agent", END: END})
    g.add_edge("agent", END)
    return g.compile()


def _known_keys() -> set:
    try:
        return load_known_parts()
    except Exception:  # noqa: BLE001  (DB caída: el router solo pierde los códigos de tamaño)
        return set()


def _reply_turn(decision: Decision, lang: str, visible_filters: Dict[str, Any], active_part_numbers: List[str],
                make_debug, title) -> Tuple[Any, ...]:
    """Respuesta determinista del router (fuera de alcance / inyección): sin LLM, sin herramientas."""
    alert = render_alert({"code": "OUT_OF_SCOPE", "params": {}}, lang)
    answer = t_router(lang, "injection" if decision.reply == "injection" else "out_of_scope")
    ui_payload = {
        "display_type": "EDGE_CASE_ALERT",
        "actuators": [],
        "engineering_warnings": [alert["message"]],
        "alerts": [alert],
        "suggested_followups": build_followups("knowledge", {"actuators": []}, lang),
    }
    parts = list(active_part_numbers)
    debug_trace, cost = make_debug([], 0, [], parts)
    meta = {
        "intent": "knowledge",
        "verification": {"status": "verified", "numbers_checked": 0, "ungrounded": []},
        "language": lang,
        "short_title": title(parts, visible_filters),
        "cost_usd": cost,
    }
    return answer, ui_payload, debug_trace, parts, visible_filters, meta


def run_agent_turn(
    user_query: str,
    history_messages: List[Dict[str, Any]],
    active_part_numbers: List[str],
    active_filters: Dict[str, Any],
    locale: Optional[str] = None,
    request_t0: Optional[float] = None,
    history_load_ms: Optional[float] = None,
) -> Tuple[str, Dict[str, Any], Dict[str, Any], List[str], Dict[str, Any], Dict[str, Any]]:
    """
    Ejecuta un turno del agente y retorna:
    (answer, ui_payload, debug_trace, updated_active_part_numbers, updated_active_filters, meta)
    meta = {intent, verification, language, short_title, cost_usd}
    Presupuesto de tiempo por turno: TURN_BUDGET_S; si se agota con resultados de herramientas se responde con la plantilla.
    """
    t0 = request_t0 if request_t0 is not None else time.perf_counter()
    deadline = t0 + TURN_BUDGET_S
    reset_turn_telemetry()
    rec = StepRecorder(t0)
    if history_load_ms is not None:
        rec.add_step("history_load", 0.0, history_load_ms)

    prev_users = [m["content"] for m in history_messages if m["role"] == "user"]
    lang = detect_language(user_query, locale, prev_users)

    # Aclaración pendiente del turno anterior: el valor elegido por el usuario se resuelve en el mismo contexto
    pending = active_filters.get("_pending") if isinstance(active_filters.get("_pending"), dict) else None
    pending_args: Dict[str, Any] = {}
    if pending and pending.get("topic"):
        answered = resolve_clarification_answer(pending["topic"], user_query)
        if answered:
            pending_args = {**(pending.get("args") or {}), **answered}
    current_pending_args.set(pending_args)
    current_user_text.set(" ".join(prev_users + [user_query]))
    visible_filters = {k: v for k, v in active_filters.items() if k != "_pending"}

    cfg = load_llm_config()
    stats: Dict[str, int] = {"llm_retries": 0}

    def _debug(all_msgs, retries, traces, parts):
        prompt_tokens, completion_tokens = _usage(all_msgs)
        cost = estimate_cost_usd(cfg, prompt_tokens, completion_tokens)
        return {
            "model_used": cfg.chat_model,
            "provider": cfg.provider,
            "total_latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "retries": retries,
                "llm_retries": stats["llm_retries"],
            },
            "active_context_part_numbers": parts,
            "tool_calls": traces,
            "steps": sorted(rec.steps, key=lambda s: s["start_ms"]),
            "cost_usd_estimate": cost,
            "language": lang,
        }, cost

    def _title(parts, filters):
        return make_short_title(parts, filters, lang, recommend=True)

    # ------------------------------------------------------------------ ROUTER determinista (sin LLM)
    r0 = time.perf_counter()
    decision: Optional[Decision] = None
    if ROUTER_ENABLED:
        try:
            decision = route(user_query, active_part_numbers, _known_keys(), pending_args)
        except Exception:  # noqa: BLE001  (una regla defectuosa nunca tumba el turno: cae al camino con LLM)
            decision = None
    rec.add_step("router", (r0 - t0) * 1000, (time.perf_counter() - r0) * 1000, detail=decision.rule if decision else "disabled")
    if decision is not None and decision.kind == "reply":
        return _reply_turn(decision, lang, visible_filters, active_part_numbers, _debug, _title)
    llm_query = decision.clean_query if decision is not None and decision.injection else user_query

    sys_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        active_parts=active_part_numbers if active_part_numbers else "None yet",
        active_filters=visible_filters if visible_filters else "None yet",
        language=LANG_NAMES[lang],
        pending=(
            f"\n   The user just answered your clarification question; pending recommendation request: {pending_args}. "
            "Call recommend_actuators now."
            if pending_args else ""
        ),
    )
    lc_messages: List[BaseMessage] = [SystemMessage(content=sys_prompt)]
    # Cargar últimos 10 mensajes de la sesión para contexto multi-turno
    for m in history_messages[-10:]:
        if m["role"] == "user":
            lc_messages.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant":
            lc_messages.append(AIMessage(content=m["content"]))
    lc_messages.append(HumanMessage(content=llm_query))

    run_cfg = {"callbacks": [rec], "configurable": {"route": True}}
    retry_cfg = {"callbacks": [rec], "configurable": {"route": False}}

    llm_failed = False
    all_msgs: List[BaseMessage] = []
    try:
        try:
            inner = create_react_agent(build_llm(), ALL_SERIES76_TOOLS)
        except Exception as exc:  # noqa: BLE001  (p. ej. sin clave): mismo manejo que un LLM caído
            raise LLMUnavailable(f"{type(exc).__name__}: {str(exc)[:120]}") from exc
        graph = build_graph(inner, decision)
        result_state = invoke_with_retry(graph, {"messages": lc_messages}, run_cfg, stats, deadline)
        all_msgs = result_state["messages"]
    except LLMUnavailable:
        llm_failed = True
        if not current_turn_tool_traces.get() and not current_turn_clarification.get():
            msg = render_alert_message("LLM_UNAVAILABLE", {}, lang)
            ui_payload = {
                "display_type": "EDGE_CASE_ALERT",
                "actuators": [],
                "engineering_warnings": [msg],
                "alerts": [render_alert({"code": "LLM_UNAVAILABLE", "params": {}}, lang)],
                "suggested_followups": [],
            }
            parts = list(active_part_numbers)
            debug_trace, cost = _debug([], 0, [], parts)
            meta = {
                "intent": "error",
                "verification": {"status": "fallback_template", "numbers_checked": 0, "ungrounded": []},
                "language": lang,
                "short_title": make_short_title(parts, visible_filters, lang),
                "cost_usd": cost,
            }
            return msg, ui_payload, debug_trace, parts, visible_filters, meta

    # ------------------------------------------------------------------ ACLARACIÓN (pregunta del asistente, sin LLM)
    if current_turn_clarification.get():
        return _clarification_turn(current_turn_clarification.get(), lang, visible_filters, active_part_numbers,
                                   all_msgs, 0, _debug, _title)

    has_cards = bool(current_turn_actuators.get())
    answer = "" if llm_failed else _polish(_last_ai_text(all_msgs), has_cards)

    # ------------------------------------------------------------------ VERIFICADOR (REGLA 4)
    retries = 0
    verifier_error = False
    template_reason: Optional[str] = None   # None | "llm_unavailable" | "too_long"
    known_parts: set = set()
    result = VerificationResult()
    first_offenders: List[str] = []
    if llm_failed:
        template_reason = "llm_unavailable"
    elif has_cards and len(answer.split()) > MAX_ANSWER_WORDS:
        template_reason = "too_long"          # una "frase" larga sin puntos que el recorte no puede partir
    else:
        v0 = time.perf_counter()
        try:
            known_parts = load_known_parts()
            result = _verify(answer, user_query, known_parts)
        except Exception:  # noqa: BLE001  (p. ej. DB caída): se devuelve la respuesta marcada como no verificada
            verifier_error = True
        rec.add_step("verifier", (v0 - t0) * 1000, (time.perf_counter() - v0) * 1000)

        if not result.ok and not verifier_error and deadline - time.perf_counter() < RETRY_MIN_BUDGET_S:
            first_offenders = result.ungrounded   # sin tiempo para reescribir: plantilla
        elif not result.ok and not verifier_error:
            retries = 1
            feedback = (
                "Your answer contains figures that are not in the tool results (or sit in the wrong field/unit/row): "
                f"{', '.join(result.ungrounded)}. Rewrite it using ONLY figures returned by the tools, each with its own unit. "
            )
            if not current_turn_tool_traces.get():
                feedback += (
                    "You have not called any tool in this turn: call lookup_actuator_by_part_number, "
                    "recommend_actuators or search_engineering_knowledge NOW"
                    + (f" (active part numbers: {', '.join(active_part_numbers)})" if active_part_numbers else "")
                    + ", then answer from its result. "
                )
            feedback += f"Reply in {LANG_NAMES[lang]}, plain text, 1-2 sentences."
            first_offenders = result.ungrounded
            v1 = time.perf_counter()
            try:
                result_state = invoke_with_retry(
                    graph, {"messages": all_msgs + [HumanMessage(content=feedback)]}, retry_cfg, stats, deadline)
                all_msgs = result_state["messages"]
                if current_turn_clarification.get():  # la herramienta pidió un dato en el reintento
                    return _clarification_turn(current_turn_clarification.get(), lang, visible_filters, active_part_numbers,
                                               all_msgs, 1, _debug, _title)
                answer = _polish(_last_ai_text(all_msgs), bool(current_turn_actuators.get()))
                if bool(current_turn_actuators.get()) and len(answer.split()) > MAX_ANSWER_WORDS:
                    template_reason = "too_long"
                else:
                    result = _verify(answer, user_query, known_parts)
            except LLMUnavailable:
                result = VerificationResult(numbers_checked=0, ungrounded=first_offenders)
            rec.add_step("verifier_retry", (v1 - t0) * 1000, (time.perf_counter() - v1) * 1000)

    status = "unverified" if verifier_error else "verified"
    ui_t = time.perf_counter()
    if decision is not None and decision.oos_note:
        current_turn_alerts.get().append({"code": "OUT_OF_SCOPE", "params": {}})
    ui_payload = build_ui_payload(list(current_turn_actuators.get().values()), lang)
    recommendation, rec_extras = build_recommendation_payload(lang)
    if recommendation is not None:
        ui_payload["recommendation"] = recommendation
        if recommendation["ranking"]:
            ui_payload["display_type"] = "RECOMMENDATION_LIST"
        elif not ui_payload["actuators"]:
            ui_payload["display_type"] = "EDGE_CASE_ALERT"
    rec.add_step("ui_payload", (ui_t - t0) * 1000, (time.perf_counter() - ui_t) * 1000)

    traces = list(current_turn_tool_traces.get())

    fallback_used = False
    if template_reason or (not result.ok and not verifier_error):
        # Plantilla determinista desde las filas de la base (sin LLM): cifras sin respaldo, texto largo o LLM caído/lento
        fb_t = time.perf_counter()
        outs = [tr.get("raw_output") for tr in traces]
        focus = next((tr["arguments"].get("focus") for tr in reversed(traces)
                      if tr["tool_name"] == "lookup_actuator_by_part_number" and tr.get("arguments")), None)
        alert_msgs = [a["message"] for a in ui_payload["alerts"] if a["code"] != "OUT_OF_SCOPE"]
        answer = build_fallback_answer(
            lang, ui_payload["actuators"], alert_msgs, outs,
            groups=infer_groups(user_query, focus),
            recommend=bool(traces) and traces[-1]["tool_name"] == "recommend_actuators",
        )
        rec.add_step("fallback_template", (fb_t - t0) * 1000, (time.perf_counter() - fb_t) * 1000, detail=template_reason or "ungrounded")
        fallback_used = True
        status = "fallback_template"
        result = VerificationResult(numbers_checked=result.numbers_checked,
                                    ungrounded=[] if template_reason else result.ungrounded)
    if decision is not None and decision.oos_note:
        answer = f"{answer} {t_router(lang, 'oos_note')}".strip()

    turn_actuators = ui_payload["actuators"]

    # Actualizar memoria de entidades activas (active_part_numbers) para el siguiente turno
    new_active_parts: List[str] = []
    for act in turn_actuators:
        bpn = act.get("base_part_number")
        if bpn and bpn not in new_active_parts:
            new_active_parts.append(bpn)
    for bpn in extract_part_numbers_from_text(answer):
        if bpn not in new_active_parts:
            new_active_parts.append(bpn)
    updated_parts = new_active_parts if new_active_parts else list(active_part_numbers)

    updated_filters = dict(visible_filters)
    for tr in traces:
        if tr["tool_name"] == "recommend_actuators" and tr.get("arguments"):
            updated_filters.update(tr["arguments"])

    intent = derive_intent(traces, fallback_used)
    ui_payload["suggested_followups"] = build_followups(
        intent, ui_payload, lang, rec_extras, asked_hz=_asked_hz(user_query)
    )

    debug_trace, cost = _debug(all_msgs, retries, traces, updated_parts)
    meta = {
        "intent": intent,
        "verification": {
            "status": status,
            "numbers_checked": result.numbers_checked,
            "ungrounded": (result.ungrounded or first_offenders) if fallback_used and not template_reason else [],
        },
        "language": lang,
        "short_title": make_short_title(updated_parts, updated_filters, lang, recommend=(intent == "recommend")),
        "cost_usd": cost,
    }
    return answer, ui_payload, debug_trace, updated_parts, updated_filters, meta
