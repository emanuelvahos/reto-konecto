try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import os
import re
import time
from typing import Any, Dict, List, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langgraph.prebuilt import create_react_agent

from app.config import load_llm_config
from app.tools import (
    ALL_SERIES76_TOOLS,
    reset_turn_telemetry,
    current_turn_tool_traces,
    current_turn_actuators,
    current_turn_alerts,
    fetch_ui_actuators,
)

SYSTEM_PROMPT_TEMPLATE = """You are the Series 76 Electric Actuators assistant for plant engineers. Every number you state must come from a tool result; never recall, compute or estimate specifications.

RULES
1. NEVER state a number unless a tool returned it IN THIS TURN. Always call lookup_actuator_by_part_number, recommend_actuators or search_engineering_knowledge first, even for follow-ups about data already shown (the app builds its spec cards from the database rows those tools return). In lookup, set `focus` only to the groups asked about ("draw/consumption" may mean current or power).
2. Active part numbers: {active_parts}. Active filters: {active_filters}. Resolve "it", "them", "compare" to the active parts.
3. Report tool figures exactly, with units (Nm and in-lbs, S4 duty %, cycles/starts per hour, speed at 60 and 50 Hz, FLA, LRA, W).
4. Edge cases:
   - MODEL_LISTED_AS_NA: say the model is N/A and present the returned alternatives.
   - TYPO_OR_CLOSEST_MATCH_FOUND / INVALID_PART_NUMBER: say the code was not found and give the closest match; if invalid, explain the part number format.
   - Torque asked without On/Off vs Modulating: cover both and explain the difference.
   - NO_EXACT_MATCH_CONSTRAINT_RELAXATION: explain the `diagnostics` and offer the closest alternatives.
   - Any `alerts` (CSA not certified, SINGLE_TORQUE_RATING...): mention them briefly. Values named single_torque_* are the single output torque of the datasheet: never call them on/off or modulating.
   - KNOWLEDGE_ERROR / NO_KNOWLEDGE_MATCH: say the information is unavailable; do not answer from memory.
5. Style: reply in the user's language, 1-2 plain sentences (max 45 words) with the key figures asked. No tables, headers, bullet lists, or tool/SQL names; the app shows the full spec card.
"""


TOOL_REMINDER = (
    "Reminder: you answered with numbers without calling a tool. Call the appropriate tool now and "
    "answer using only its results."
)
UNVERIFIED_ANSWER = (
    "No pude verificar esa información en la base de datos del catálogo. "
    "Por favor reformula tu consulta indicando el número de parte o los requisitos."
)


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


def _has_digits(text: str) -> bool:
    return re.search(r"\d", text) is not None


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


def build_ui_payload(actuator_ids: List[Any]) -> Dict[str, Any]:
    """ui_payload construido solo con filas de PostgreSQL y alertas de las tools; nada sale del texto del LLM."""
    actuators = fetch_ui_actuators(actuator_ids)
    alerts: List[Dict[str, str]] = [dict(a) for a in current_turn_alerts.get()]

    for act in actuators:
        if not act.get("csa_certified", True):
            msg = f"Model {act['base_part_number']} (Frame Size {act['frame_size']}) is NOT CSA Certified (CE & UKCA only)."
            if not any(a["message"] == msg for a in alerts):
                alerts.append({"code": "CSA_NOT_CERTIFIED", "severity": "warning", "message": msg})

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


def run_agent_turn(
    user_query: str,
    history_messages: List[Dict[str, Any]],
    active_part_numbers: List[str],
    active_filters: Dict[str, Any],
) -> Tuple[str, Dict[str, Any], Dict[str, Any], List[str], Dict[str, Any]]:
    """
    Ejecuta un turno del agente LangChain/LangGraph y retorna:
    (answer, ui_payload, debug_trace, updated_active_part_numbers, updated_active_filters)
    """
    t0 = time.perf_counter()
    reset_turn_telemetry()

    llm = build_llm()
    agent_executor = create_react_agent(llm, ALL_SERIES76_TOOLS)

    sys_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        active_parts=active_part_numbers if active_part_numbers else "None yet",
        active_filters=active_filters if active_filters else "None yet",
    )

    lc_messages: List[BaseMessage] = [SystemMessage(content=sys_prompt)]
    # Cargar últimos 10 mensajes de la sesión para contexto multi-turno
    for m in history_messages[-10:]:
        if m["role"] == "user":
            lc_messages.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant":
            lc_messages.append(AIMessage(content=m["content"]))

    lc_messages.append(HumanMessage(content=user_query))

    result_state = agent_executor.invoke({"messages": lc_messages})
    all_msgs: List[BaseMessage] = result_state["messages"]
    retries = 0
    if not current_turn_tool_traces.get() and _has_digits(_last_ai_text(all_msgs)):
        # Guarda anti-alucinación: cifras sin ninguna herramienta en este turno -> un reintento forzando herramienta
        retries = 1
        reset_turn_telemetry()
        result_state = agent_executor.invoke(
            {"messages": lc_messages + [HumanMessage(content=TOOL_REMINDER)]}
        )
        all_msgs = result_state["messages"]

    # Extraer respuesta final del último AIMessage
    prompt_tokens = 0
    completion_tokens = 0

    for msg in all_msgs:
        if isinstance(msg, AIMessage):
            usage = getattr(msg, "usage_metadata", None) or msg.response_metadata.get("token_usage", {})
            if usage:
                prompt_tokens += usage.get("input_tokens") or usage.get("prompt_tokens") or 0
                completion_tokens += usage.get("output_tokens") or usage.get("completion_tokens") or 0

    final_answer = _last_ai_text(all_msgs)
    if not current_turn_tool_traces.get() and _has_digits(final_answer):
        # Sigue sin herramienta: no se muestra ninguna cifra que no venga de la base de datos
        final_answer = UNVERIFIED_ANSWER

    traces = list(current_turn_tool_traces.get())
    ui_payload = build_ui_payload(list(current_turn_actuators.get().values()))
    turn_actuators = ui_payload["actuators"]

    # Actualizar memoria de entidades activas (active_part_numbers) para el siguiente turno
    new_active_parts: List[str] = []
    for act in turn_actuators:
        bpn = act.get("base_part_number")
        if bpn and bpn not in new_active_parts:
            new_active_parts.append(bpn)

    for bpn in extract_part_numbers_from_text(final_answer):
        if bpn not in new_active_parts:
            new_active_parts.append(bpn)

    updated_parts = new_active_parts if new_active_parts else list(active_part_numbers)

    # Actualizar filtros activos si se llamó a recommend_actuators
    updated_filters = dict(active_filters)
    for tr in traces:
        if tr["tool_name"] == "recommend_actuators" and tr.get("arguments"):
            updated_filters.update(tr["arguments"])

    total_ms = round((time.perf_counter() - t0) * 1000, 2)

    cfg = load_llm_config()
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
    }

    return final_answer, ui_payload, debug_trace, updated_parts, updated_filters
