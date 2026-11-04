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

from app.tools import (
    ALL_SERIES76_TOOLS,
    reset_turn_telemetry,
    current_turn_tool_traces,
    current_turn_actuators,
)

SYSTEM_PROMPT_TEMPLATE = """You are the Series 76 Electric Actuators Technical Engineering Assistant for a plant engineering team.
Your ONLY source of truth for actuator numbers and specifications is the PostgreSQL database queried through your tools.

STRICT ENGINEERING & ZERO-HALLUCINATION RULES:
1. NEVER invent, guess, or recall numbers from pre-training. Always call `lookup_actuator_by_part_number`, `recommend_actuators`, or `search_engineering_knowledge` first.
2. EXACT NUMBERS: Report exact figures from the tool output (Torque in Nm and in-lbs, Duty Cycle S4%, Cycles/Starts per hour, Operating Speed at 60Hz and 50Hz, FLA, LRA, and Motor Power in Watts).
3. MULTI-TURN COREFERENCE:
   - Currently active part numbers in this conversation session: {active_parts}
   - Active technical filters from previous turns: {active_filters}
   - If the user asks a follow-up question like "and how much power does it draw?", "what is its LRA at 50Hz?", or "compare them", immediately resolve "it" or "them" to the active part numbers above.
   - Even if the actuator data appeared in a previous message, ALWAYS invoke `lookup_actuator_by_part_number` (or `recommend_actuators`) again on follow-up questions so the current turn's `ui_payload` and `debug_trace` are freshly populated from PostgreSQL.
4. EDGE CASES HANDLING:
   - N/A Models: In 220V 3-Phase, sizes 761A, 761B, 762A, and 762B (`-11330C00/A`) are explicitly listed as N/A. State clearly that the model is N/A in 220V 3-Phase and present the single-phase alternatives returned by the tool.
   - Typos / Invalid Part Numbers: If a user provides a typo (e.g., `761800` instead of `761B00`), politely clarify that the exact code was not found, show the closest match found by fuzzy search, and provide its specs. If completely invalid, explain the valid Series 76 part number format.
   - Ambiguous Queries: If the user asks for a torque recommendation without specifying On/Off vs Modulating service (or 50Hz vs 60Hz), provide the matching models for both services and explicitly explain the difference between On/Off torque and Modulating torque ratings.
   - Impossible Requirements: If no model meets all requirements, use the `diagnostics` and `closest_alternative_actuators` from the tool to explain which physical limit was exceeded and recommend the closest viable options.
   - CSA Certification Warning: Always warn the user if a recommended model is Size 6 or Size 7 (`766A00`, `766B00`, `767A00`, `767B00`, `767C00`), noting that Sizes 6 and 7 are NOT CSA Certified (CE & UKCA only).
5. FORMATTING & EXECUTIVE BREVITY (NO REDUNDANT LISTS OR TABLES):
   - NEVER output Markdown tables (`| col | col |`), `###` headers, or vertical bullet lists (`- Metric: Value`) repeating all specifications when a tool returns actuators in `ui_payload`. The mobile app automatically renders an interactive native specification card / comparison table with all electrical and mechanical details right below your message.
   - Keep your textual response strictly to a direct, executive 1-2 sentence summary in fluid prose (maximum 45 words).
   - In those 1-2 prose sentences, directly state the core answer and mention the primary figures queried (for example: on/off and modulating torques like 500 Nm / 380 Nm, motor power like 90 W, or speed/current) naturally in the sentence without bullet formatting.
   - Never mention internal tool names, function calls, or SQL queries in your answer.
"""


def build_llm() -> ChatOpenAI:
    base_url = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    api_key = os.getenv("LLM_API_KEY", "")
    model_name = os.getenv("LLM_CHAT_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.0,
        max_tokens=1200,
        timeout=40.0,
    )


def extract_part_numbers_from_text(text: str) -> List[str]:
    pattern = r"\b76[1-7][ABCXY](?:00|30)-113(?:[0278]0000|30C00)/A\b"  # 3-fase: 11330C00
    return list(dict.fromkeys(re.findall(pattern, text.upper())))


def build_ui_payload(
    actuators: List[Dict[str, Any]],
    traces: List[Dict[str, Any]],
) -> Dict[str, Any]:
    warnings: List[str] = []

    for act in actuators:
        if not act.get("csa_certified", True):
            w = f"Model {act['base_part_number']} (Frame Size {act['frame_size']}) is NOT CSA Certified (CE & UKCA only)."
            if w not in warnings:
                warnings.append(w)

    for tr in traces:
        out = tr.get("raw_output") or {}
        if isinstance(out, dict):
            if out.get("status") in (
                "MODEL_LISTED_AS_NA",
                "TYPO_OR_CLOSEST_MATCH_FOUND",
                "INVALID_PART_NUMBER",
                "NO_EXACT_MATCH_CONSTRAINT_RELAXATION",
            ):
                msg = out.get("message")
                if msg and msg not in warnings:
                    warnings.append(msg)
            for d in out.get("diagnostics", []):
                if d not in warnings:
                    warnings.append(d)
            for amb in out.get("ambiguity_warnings", []):
                if amb not in warnings:
                    warnings.append(amb)

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

    # Extraer respuesta final del último AIMessage
    final_answer = ""
    prompt_tokens = 0
    completion_tokens = 0

    for msg in all_msgs:
        if isinstance(msg, AIMessage):
            usage = getattr(msg, "usage_metadata", None) or msg.response_metadata.get("token_usage", {})
            if usage:
                prompt_tokens += usage.get("input_tokens") or usage.get("prompt_tokens") or 0
                completion_tokens += usage.get("output_tokens") or usage.get("completion_tokens") or 0

    for msg in reversed(all_msgs):
        if isinstance(msg, AIMessage) and msg.content:
            content = msg.content
            if isinstance(content, list):
                content = "\n".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
            final_answer = str(content).strip()
            if final_answer:
                break

    traces = list(current_turn_tool_traces.get())
    actuators_dict_or_list = current_turn_actuators.get()
    if isinstance(actuators_dict_or_list, dict):
        turn_actuators = list(actuators_dict_or_list.values())
    else:
        turn_actuators = list(actuators_dict_or_list)

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

    ui_payload = build_ui_payload(turn_actuators, traces)
    total_ms = round((time.perf_counter() - t0) * 1000, 2)

    model_used = os.getenv("LLM_CHAT_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
    debug_trace = {
        "model_used": model_used,
        "total_latency_ms": total_ms,
        "token_usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "active_context_part_numbers": updated_parts,
        "tool_calls": traces,
    }

    return final_answer, ui_payload, debug_trace, updated_parts, updated_filters
