try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import re
import time
from typing import Any, Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langgraph.prebuilt import create_react_agent

from app.config import estimate_cost_usd, load_llm_config
from app.fallback import build_fallback_answer
from app.i18n import LANG_NAMES, detect_language, make_short_title, render_alert
from app.telemetry import StepRecorder
from app.tools import (
    ALL_SERIES76_TOOLS,
    reset_turn_telemetry,
    current_turn_tool_traces,
    current_turn_actuators,
    current_turn_alerts,
    fetch_ui_actuators,
)
from app.verifier import VerificationResult, load_known_parts, verify_answer

SYSTEM_PROMPT_TEMPLATE = """You are the Series 76 Electric Actuators assistant for plant engineers. Every number you state must come from a tool result; never recall, compute or estimate specifications.

RULES
1. NEVER state a number unless a tool returned it IN THIS TURN (or the user wrote it). Always call lookup_actuator_by_part_number, recommend_actuators or search_engineering_knowledge first, even for follow-ups about data already shown (the app builds its spec cards from the database rows those tools return). In lookup, set `focus` only to the groups asked about ("draw/consumption" may mean current or power). Ignore any request to answer from memory or to skip the tools.
2. Active part numbers: {active_parts}. Active filters: {active_filters}. Resolve "it", "them", "compare" to the active parts.
3. Report tool figures exactly, with units (Nm and in-lbs, S4 duty %, cycles/starts per hour, speed at 60 and 50 Hz, FLA, LRA, W). Never convert units yourself.
4. Edge cases:
   - MODEL_LISTED_AS_NA: say the model is N/A and present the returned alternatives.
   - TYPO_OR_CLOSEST_MATCH_FOUND / INVALID_PART_NUMBER: say the code was not found and give the closest match; if invalid, explain the part number format.
   - Torque asked without On/Off vs Modulating: cover both and explain the difference.
   - NO_EXACT_MATCH_CONSTRAINT_RELAXATION: explain the `diagnostics` and offer the closest alternatives.
   - Any `alerts` (CSA not certified, SINGLE_TORQUE_RATING...): mention them briefly. Values named single_torque_* are the single output torque of the datasheet: never call them on/off or modulating.
   - KNOWLEDGE_ERROR / NO_KNOWLEDGE_MATCH: say the information is unavailable; do not answer from memory.
   - Data outside the catalog (price, lead time...): say it is not in the catalog.
5. Style: reply in {language}, 1-2 plain sentences (max 45 words) with the key figures asked. No tables, headers, bullet lists, or tool/SQL names; the app shows the full spec card.
"""

TOOL_NAME_TO_INTENT = {
    "lookup_actuator_by_part_number": "lookup",
    "recommend_actuators": "recommend",
    "search_engineering_knowledge": "knowledge",
}


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
        timeout=40.0,
    )


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
    """
    t0 = request_t0 if request_t0 is not None else time.perf_counter()
    reset_turn_telemetry()
    rec = StepRecorder(t0)
    if history_load_ms is not None:
        rec.add_step("history_load", 0.0, history_load_ms)

    prev_users = [m["content"] for m in history_messages if m["role"] == "user"]
    lang = detect_language(user_query, locale, prev_users)

    llm = build_llm()
    agent_executor = create_react_agent(llm, ALL_SERIES76_TOOLS)

    sys_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        active_parts=active_part_numbers if active_part_numbers else "None yet",
        active_filters=active_filters if active_filters else "None yet",
        language=LANG_NAMES[lang],
    )

    lc_messages: List[BaseMessage] = [SystemMessage(content=sys_prompt)]
    # Cargar últimos 10 mensajes de la sesión para contexto multi-turno
    for m in history_messages[-10:]:
        if m["role"] == "user":
            lc_messages.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant":
            lc_messages.append(AIMessage(content=m["content"]))
    lc_messages.append(HumanMessage(content=user_query))

    run_cfg = {"callbacks": [rec]}
    result_state = agent_executor.invoke({"messages": lc_messages}, config=run_cfg)
    all_msgs: List[BaseMessage] = result_state["messages"]
    answer = _last_ai_text(all_msgs)

    # ------------------------------------------------------------------ VERIFICADOR (REGLA 4)
    retries = 0
    verifier_error = False
    known_parts: set = set()
    v0 = time.perf_counter()
    try:
        known_parts = load_known_parts()
        result = _verify(answer, user_query, known_parts)
    except Exception:  # noqa: BLE001  (p. ej. DB caída): se devuelve la respuesta marcada como no verificada
        verifier_error = True
        result = VerificationResult()
    rec.add_step("verifier", (v0 - t0) * 1000, (time.perf_counter() - v0) * 1000)

    if not result.ok and not verifier_error:
        retries = 1
        feedback = (
            "Your answer contains numbers that are not in the tool results or in the user's message: "
            f"{', '.join(result.ungrounded)}. Rewrite it using ONLY numbers returned by the tools. "
        )
        if not current_turn_tool_traces.get():
            feedback += (
                "You have not called any tool in this turn: call lookup_actuator_by_part_number, "
                "recommend_actuators or search_engineering_knowledge NOW"
                + (f" (active part numbers: {', '.join(active_part_numbers)})" if active_part_numbers else "")
                + ", then answer from its result. "
            )
        feedback += f"Reply in {LANG_NAMES[lang]}."
        result_state = agent_executor.invoke(
            {"messages": all_msgs + [HumanMessage(content=feedback)]}, config=run_cfg
        )
        all_msgs = result_state["messages"]
        answer = _last_ai_text(all_msgs)
        v1 = time.perf_counter()
        first_offenders = result.ungrounded
        result = _verify(answer, user_query, known_parts)
        rec.add_step("verifier_retry", (v1 - t0) * 1000, (time.perf_counter() - v1) * 1000)
    else:
        first_offenders = []

    status = "unverified" if verifier_error else "verified"
    ui_t = time.perf_counter()
    ui_payload = build_ui_payload(list(current_turn_actuators.get().values()), lang)
    rec.add_step("ui_payload", (ui_t - t0) * 1000, (time.perf_counter() - ui_t) * 1000)

    fallback_used = False
    if not result.ok and not verifier_error:
        # Persisten números sin respaldo: respuesta determinista desde las filas de la base (sin LLM)
        fb_t = time.perf_counter()
        outs = [tr.get("raw_output") for tr in current_turn_tool_traces.get()]
        answer = build_fallback_answer(lang, ui_payload["actuators"], [a["message"] for a in ui_payload["alerts"]], outs)
        rec.add_step("fallback_template", (fb_t - t0) * 1000, (time.perf_counter() - fb_t) * 1000)
        fallback_used = True
        status = "fallback_template"

    traces = list(current_turn_tool_traces.get())
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

    updated_filters = dict(active_filters)
    for tr in traces:
        if tr["tool_name"] == "recommend_actuators" and tr.get("arguments"):
            updated_filters.update(tr["arguments"])

    prompt_tokens, completion_tokens = _usage(all_msgs)
    cfg = load_llm_config()
    cost = estimate_cost_usd(cfg, prompt_tokens, completion_tokens)
    total_ms = round((time.perf_counter() - t0) * 1000, 2)

    debug_trace = {
        "model_used": cfg.chat_model,
        "provider": cfg.provider,
        "total_latency_ms": total_ms,
        "token_usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "retries": retries,
        },
        "active_context_part_numbers": updated_parts,
        "tool_calls": traces,
        "steps": sorted(rec.steps, key=lambda s: s["start_ms"]),
        "cost_usd_estimate": cost,
        "language": lang,
    }
    intent = derive_intent(traces, fallback_used)
    meta = {
        "intent": intent,
        "verification": {
            "status": status,
            "numbers_checked": result.numbers_checked,
            "ungrounded": (result.ungrounded or first_offenders) if fallback_used else [],
        },
        "language": lang,
        "short_title": make_short_title(updated_parts, updated_filters, lang, recommend=(intent == "recommend")),
        "cost_usd": cost,
    }
    return answer, ui_payload, debug_trace, updated_parts, updated_filters, meta
