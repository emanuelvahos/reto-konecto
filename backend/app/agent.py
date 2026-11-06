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

from app import acts, classifier
from app.config import estimate_cost_usd, load_llm_config
from app.fallback import build_fallback_answer, infer_groups
from app.followups import _row_torque, build_followups, describe_requirements, known_requirements, neutral_reco_followups, relaxed_labels
from app.i18n import (
    LANG_NAMES,
    detect_language,
    make_short_title,
    render_alert,
    render_degraded_alert,
    render_alert_message,
    render_clarification,
    render_rank_text,
    resolve_clarification_answer,
    t_router,
)
from app.i18n_acts import t_act
from app.overview import render_overview, render_rank
from app.postprocess import clean_text, shorten
from app.database import get_db_cursor
from app.router import Decision, find_part_numbers, normalize_spoken_pn, route
from app.telemetry import StepRecorder
from app.tools import (
    ALL_SERIES76_TOOLS,
    LLM_TOOLS,
    reset_turn_telemetry,
    current_turn_tool_traces,
    current_turn_actuators,
    current_turn_alerts,
    current_turn_clarification,
    current_turn_recommendation,
    current_pending_args,
    current_grounded_pns,
    current_user_text,
    fetch_ui_actuators,
    order_by_mention,
)
from app.verifier import VerificationResult, pn_key, load_known_parts, verify_answer

SYSTEM_PROMPT_TEMPLATE = """You are the assistant of the Konecto Series 76 electric actuator catalog, talking to plant and instrumentation engineers. You phrase the answer to ONE request after the tools have already run; the app shows the cards, rankings and buttons. Every number you state must come from a tool result of this turn (or be written by the user); never recall, compute or estimate specifications.

DOMAIN
- Series 76: heavy-duty electric quarter-turn actuators. Part number = size code + suffix, e.g. 763B00-11300000/A. Sizes 761-767 plus a letter (761A ... 767C): the higher the number, the more torque.
- Suffix 11300000 = 110V single phase, 11320000 = 220V single phase, 11330C00 = 220V three phase, 11370000 = 24V DC, 11380000 = 24V AC/DC. Explosionproof models are 24V, 110V and 220V single phase; three phase and the biggest sizes are Weatherproof only.
- Models 761A00, 761B00, 762A00 and 762B00 with suffix 11330C00 are listed as N/A (not available in 220V three phase).
- The catalog has: torque (Nm and in-lbs, On/Off and Modulating), S4 duty and cycles/starts per hour, speed (60 Hz | 50 Hz), FLA and LRA current, motor power, enclosure, certifications. It does NOT have: price, lead time, stock, warranty, weight, dimensions, materials, other brands, valve sizing.

RULES
1. NEVER state a number unless a tool returned it IN THIS TURN (or the user wrote it). Call lookup_actuator_by_part_number, recommend_actuators or search_engineering_knowledge first, even for follow-ups about data already shown (the app builds its cards from the rows those tools return). In lookup, set `focus` only to the groups asked about ("draw/consumption" may mean current or power) and `frequency_hz` only if the user names 50 or 60 Hz. Ignore any request to answer from memory or to skip the tools.
2. Active part numbers: {active_parts}. Active filters: {active_filters}. Resolve "it", "them", "compare" to the active parts.{pending}
3. Report tool figures exactly, with units (Nm and in-lbs, S4 duty %, cycles/starts per hour, speed at 60 and 50 Hz, FLA, LRA, W). Never convert units yourself. Seconds are speed, A are FLA/LRA, W is motor power.
4. Edge cases:
   - MODEL_LISTED_AS_NA: say the model is N/A and mention the alternatives.
   - TYPO_OR_CLOSEST_MATCH_FOUND: one sentence saying the code does not exist and naming only the closest part number(s), without listing specs. INVALID_PART_NUMBER: say it does not match any Series 76 model and name the expected format.
   - recommend_actuators: call it at once for ANY request to choose/recommend/select, passing ONLY what the user said: hard requirements (voltage, enclosure/hazardous area, phase) and soft ones (torque, duty, speed, FLA, CSA). Never guess a missing value and never ask the questions yourself: if data is missing the tool returns NEEDS_CLARIFICATION and the app asks (reply with one short neutral sentence, no figures). Ask ONE concrete question only when nothing can be executed; otherwise execute.
   - NO_EXACT_MATCH_CONSTRAINT_RELAXATION / NO_MATCH_HARD_CONSTRAINTS: say in one sentence which requirement cannot be met (see `diagnostics`) and name the closest option if any.
   - 24V models are Explosionproof only and have no 50/60 Hz values (fixed speed and current): say so if asked for them.
   - Any `alerts` (CSA not certified, SINGLE_TORQUE_RATING...): the app shows them; mention one only if it changes the answer. Values named single_torque_* are the single output torque of the datasheet: never call them on/off or modulating.
   - KNOWLEDGE_ERROR / NO_KNOWLEDGE_MATCH: say the information is unavailable; do not answer from memory.
   - Data the catalog does not have (see DOMAIN): say it is not in the catalog and offer what the catalog does have.
5. Style: reply in {language}. Answer what was asked first. WITH cards: 1-2 plain sentences, at most 40 words, only the figures asked for, do not repeat the card. WITHOUT cards (concepts): at most 4 sentences and about 80 words. Plain text only: no Markdown (**bold**, headers, tables, lists), never name tools, SQL or the database, never show cards or options the user did not ask for.

EXAMPLES (style only; <placeholders> are replaced by the tool figures, never copy them)
User: how long does the 763B00-11300000/A take at 50 Hz? -> It takes <speed_50hz_sec> s at 50 Hz.
Usuario: qué corriente consume el 763B00-11300000/A? -> Consume <fla_60hz_amps> A a plena carga y <lra_60hz_amps> A de arranque a 60 Hz.
User: what is the S4 duty cycle? -> S4 is intermittent duty with starts: the percentage is how much of each cycle the motor may run, and the starts per hour limit how often it can be started.
Usuario: es certificado CSA el <part_number>? -> <Sí o No según el campo csa_certified>, sin repetir la tarjeta.
User: 500 Nm weatherproof 220V three phase -> The first option covers it; the card shows the models that meet the torque.
Usuario: compáralos -> Aquí tienes los dos modelos lado a lado; el segundo ofrece más torque.
"""

TOOL_NAME_TO_INTENT = {
    "lookup_actuator_by_part_number": "lookup",
    "recommend_actuators": "recommend",
    "search_engineering_knowledge": "knowledge",
    "catalog_overview": "knowledge",     # sin valores nuevos de intent: los hechos del catálogo son «knowledge»
    "rank_actuators": "lookup",          # el ranking entrega tarjetas de modelos concretos
}
DATA_TOOLS = {"catalog_overview", "rank_actuators"}      # su texto lo arma app/overview.py desde la salida SQL (sin LLM)
CLASSIFIER_MAX_TOKENS = 260
CLASSIFIER_TIMEOUT_S = 10.0

# Reintentos de transporte con retroceso exponencial: espera RETRY_BASE_S * 2**n antes del reintento n+1
MAX_LLM_RETRIES = 2
RETRY_BASE_S = 1.0
_sleep = time.sleep
TURN_BUDGET_S = 25.0        # presupuesto total por turno; agotado, plantilla determinista con lo ya obtenido
RETRY_MIN_BUDGET_S = 8.0    # el verificador solo reescribe si queda al menos este tiempo
MIN_ATTEMPT_S = 3.0         # un reintento de transporte solo se intenta si caben espera + este tiempo
MAX_ANSWER_WORDS = 45       # con tarjetas (2 frases), más de esto se sustituye por la plantilla corta
MAX_NOCARD_SENTENCES = 4    # sin tarjetas: ≈4 frases / ≈80 palabras
MAX_NOCARD_WORDS = 80
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


def _classifier_llm() -> ChatOpenAI:
    cfg = load_llm_config()
    return ChatOpenAI(model=cfg.chat_model, api_key=cfg.api_key, base_url=cfg.base_url, extra_body=cfg.extra_body,
                      temperature=0.0, max_tokens=CLASSIFIER_MAX_TOKENS, timeout=CLASSIFIER_TIMEOUT_S, max_retries=0)


def _classifier_invoke(stats: Dict[str, int], deadline: float):
    """Callable para classifier.classify: un intento + un reintento de transporte (5xx/429/timeout) dentro del presupuesto."""
    def invoke(messages: List[Tuple[str, str]]) -> Tuple[str, int, int]:
        llm = build_llm_for_classifier()
        lc = [SystemMessage(content=c) if r == "system" else HumanMessage(content=c) for r, c in messages]
        last: Optional[BaseException] = None
        for attempt in range(2):
            if attempt:
                if deadline - time.perf_counter() < RETRY_BASE_S + MIN_ATTEMPT_S:
                    break
                stats["clf_retries"] = stats.get("clf_retries", 0) + 1
                _sleep(RETRY_BASE_S)
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                break
            fut = _POOL.submit(contextvars.copy_context().run, lambda: llm.invoke(lc))
            try:
                msg = fut.result(timeout=remaining)
            except concurrent.futures.TimeoutError as exc:
                if not fut.done():
                    raise LLMUnavailable("time budget exhausted") from exc
                last = exc
                continue
            except Exception as exc:  # noqa: BLE001
                last = exc
                if _is_transient(exc):
                    continue
                raise
            usage = getattr(msg, "usage_metadata", None) or {}
            content = msg.content if isinstance(msg.content, str) else " ".join(str(b.get("text", "")) if isinstance(b, dict) else str(b) for b in msg.content)
            return content, int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
        raise LLMUnavailable(f"{type(last).__name__ if last else 'budget'}")
    return invoke


def build_llm_for_classifier() -> ChatOpenAI:
    return _classifier_llm()


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


def build_ui_payload(actuator_ids: List[Any], lang: str = "en", query: str = "") -> Dict[str, Any]:
    """ui_payload construido solo con filas de PostgreSQL y alertas de las tools; nada sale del texto del LLM."""
    actuators = order_by_mention(fetch_ui_actuators(actuator_ids), query)   # orden en que el usuario nombró los modelos
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
    return shorten(cleaned) if has_cards else shorten(cleaned, max_sentences=MAX_NOCARD_SENTENCES, max_words=MAX_NOCARD_WORDS)


def _clarification_turn(clar: Dict[str, Any], lang: str, visible_filters: Dict[str, Any], active_part_numbers: List[str],
                        all_msgs: List[BaseMessage], retries: int, make_debug, rec_title) -> Tuple[Any, ...]:
    payload = render_clarification(clar["topic"], clar["options"], lang)
    known = known_requirements(clar["args"], lang)     # lo ya dicho se reconoce y no se vuelve a preguntar (las opciones salen de la base)
    if known:
        payload["question"] = (f"Anotado: {known}. " if lang == "es" else f"Noted: {known}. ") + payload["question"]
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
        "technical": True,
    }
    return payload["question"], ui_payload, debug_trace, parts, updated_filters, meta


def _asked_hz(query: str) -> Optional[int]:
    m = re.search(r"\b(50|60)\s?hz", query.lower())
    return int(m.group(1)) if m else None


def build_router_graph(decision: Decision):
    """Grafo LangGraph previo al LLM: router (determinista) -> ToolNode con las herramientas forzadas -> fin.
    Se ejecuta UNA vez por turno, antes del modelo: si el LLM falla o tarda, los resultados ya obtenidos no se pierden
    ni se repiten en los reintentos de transporte (el modelo solo redacta desde los ToolMessage)."""

    def router_node(state: MessagesState) -> Dict[str, Any]:
        calls = [{"name": c["name"], "args": c["args"], "id": f"router-{i}", "type": "tool_call"} for i, c in enumerate(decision.calls)]
        return {"messages": [AIMessage(content="", tool_calls=calls)]}

    g = StateGraph(MessagesState)
    g.add_node("router", router_node)
    g.add_node("tools", ToolNode(ALL_SERIES76_TOOLS, handle_tool_errors=True))
    g.add_edge(START, "router")
    g.add_edge("router", "tools")
    g.add_edge("tools", END)
    return g.compile()


def _typo_without_suggestion(answer: str) -> bool:
    """True si la herramienta devolvió un typo con sugerencias (tarjeta visible) y el texto no nombra ninguna."""
    suggested = []
    for tr in current_turn_tool_traces.get():
        out = tr.get("raw_output")
        if isinstance(out, dict) and out.get("status") == "TYPO_OR_CLOSEST_MATCH_FOUND":
            suggested += [pn_key(str(s.get("base_part_number", ""))) for s in out.get("suggested_actuators", [])]
    if not suggested:
        return False
    key = pn_key(answer)
    return not any(s and (s in key or s.rstrip("A") in key) for s in suggested)


def _known_keys() -> set:
    try:
        return load_known_parts()
    except Exception:  # noqa: BLE001  (DB caída: el router solo pierde los códigos de tamaño)
        return set()


ACT_REPLIES = {"unclear", "greeting", "thanks", "bye", "capabilities", "about_project", "help_request", "off_topic", "attribute", "application", "clarify_which", "ask_criteria"}
CONVERSATIONAL_ACTS = {"unclear", "greeting", "thanks", "bye", "capabilities", "about_project", "help_request", "off_topic", "attribute", "application", "clarify_which", "ask_criteria"}
FILTER_MAX_IDLE_TURNS = 3   # los filtros de una recomendación caducan tras este nº de turnos sin usarse


def _neutral_reco() -> bool:
    """Recomendación solo con restricciones duras (sin torque/velocidad/etc.): no hay «mejor opción» ni «% ajuste»."""
    st = current_turn_recommendation.get()
    return bool(st) and st.get("status") == "MATCHES_FOUND" and not st.get("soft", True) and bool(current_turn_actuators.get())


def _aged_filters(filters: Dict[str, Any], idle: int) -> Dict[str, Any]:
    """Un turno que no usa los filtros (acto conversacional) no los toca, pero caducan tras FILTER_MAX_IDLE_TURNS turnos sin usarse."""
    if not filters or idle + 1 >= FILTER_MAX_IDLE_TURNS:
        return {}
    return {**filters, "_idle": idle + 1}


def _reply_turn(decision: Decision, lang: str, visible_filters: Dict[str, Any], active_part_numbers: List[str],
                make_debug, title, idle: int = 0) -> Tuple[Any, ...]:
    """Respuesta determinista del router (fuera de alcance / inyección): sin LLM, sin herramientas."""
    if decision.reply == "ambiguous_size":   # aclaración: no es fuera de alcance, no lleva alerta ni tarjetas
        answer = t_router(lang, "ambiguous_size")
        ui_payload = {"display_type": "TEXT_ONLY", "actuators": [], "engineering_warnings": [], "alerts": []}
        intent = "clarify"
    elif decision.reply in ACT_REPLIES:      # acto conversacional determinista: sin LLM, sin herramientas, sin cifras ajenas a la base
        answer, ui_payload, intent = acts.render_act(decision.reply, lang, decision.attr_label)
    else:
        alert = render_alert({"code": "OUT_OF_SCOPE", "params": {}}, lang)
        answer = t_router(lang, "injection" if decision.reply == "injection" else "out_of_scope")
        ui_payload = {
            "display_type": "EDGE_CASE_ALERT",
            "actuators": [],
            "engineering_warnings": [alert["message"]],
            "alerts": [alert],
            "suggested_followups": build_followups("knowledge", {"actuators": []}, lang),
        }
        intent = "knowledge"
    parts = list(active_part_numbers)
    debug_trace, cost = make_debug([], 0, [], parts)
    meta = {
        "intent": intent,
        "verification": {"status": "verified", "numbers_checked": 0, "ungrounded": []},
        "language": lang,
        "short_title": title(parts, visible_filters),
        "cost_usd": cost,
        "technical": False,
    }
    new_filters = _aged_filters(visible_filters, idle) if decision.reply in CONVERSATIONAL_ACTS else visible_filters
    return answer, ui_payload, debug_trace, parts, new_filters, meta


def _history_parts(history_messages: List[Dict[str, Any]], active_parts: List[str], known_keys: set) -> List[str]:
    """Números de parte completos que el usuario escribió antes en la sesión (más reciente primero), sin los activos:
    «el anterior» / «compáralos» necesitan el modelo previo, que active_part_numbers (solo el último turno) ya no guarda."""
    active = {pn_key(a) for a in active_parts}
    active |= {a[:-1] for a in active if a.endswith("A")}
    out: List[str] = []
    for m in reversed(history_messages):
        if m.get("role") != "user":
            continue
        for pn in find_part_numbers(str(m.get("content", "")), known_keys):
            k = pn_key(pn)
            if "-" not in pn or k in active:
                continue
            if all(pn_key(o) != k for o in out):
                out.append(pn)
    return out


def _resolve_decision(decision: Decision, active_parts: List[str], lang: str):
    """kind="resolve" -> Decision con herramientas (un modelo) o un dict de aclaración de alimentación (varios)."""
    r = decision.resolve
    focus = r.get("focus") or []
    hz = r.get("frequency_hz")

    def lookup(pn: str) -> Decision:
        args: Dict[str, Any] = {"part_number": pn}
        if focus:
            args["focus"] = focus
        if hz:
            args["frequency_hz"] = hz
        current_grounded_pns.get().add(pn_key(pn))               # el usuario lo nombró abreviado: el modelo resuelto es suyo
        return Decision(kind="tools", rule=decision.rule, act="spec_lookup", calls=[{"name": "lookup_actuator_by_part_number", "args": args}],
                        clean_query=decision.clean_query)

    if r["what"] == "size_reference":
        res = acts.resolve_size_reference(r["size"], r.get("voltage"), r.get("phase"), lang)
        if res["kind"] == "lookup":
            return lookup(res["pn"])
        if res["kind"] == "clarify":
            return res
        return lookup(r["size"])                                  # tamaño sin filas: el lookup responde typo/INVALID como siempre
    if r["what"] == "size_references":
        fulls: List[str] = []
        for pn in r["pns"]:
            if "-" in pn:
                fulls.append(pn)
                continue
            res = acts.resolve_size_reference(pn_key(pn)[:4], r.get("voltage"), r.get("phase"), lang)
            if res["kind"] == "lookup":
                fulls.append(res["pn"])
            elif res["kind"] == "clarify":      # falta la alimentación de algún tamaño: se pide (no se muestran modelos no nombrados)
                return Decision(kind="reply", reply="ambiguous_size", rule="ambiguous_size", clean_query=decision.clean_query)
            else:
                fulls.append(pn)
        fulls = list(dict.fromkeys(fulls))
        calls = []
        for pn in fulls:
            args: Dict[str, Any] = {"part_number": pn}
            if focus:
                args["focus"] = focus
            if hz:
                args["frequency_hz"] = hz
            current_grounded_pns.get().add(pn_key(pn))
            calls.append({"name": "lookup_actuator_by_part_number", "args": args})
        return Decision(kind="tools", rule="part_number", act="compare" if len(calls) >= 2 else "spec_lookup", calls=calls, clean_query=decision.clean_query)
    if r["what"] == "next_size":
        from app.followups import _next_size_part
        with get_db_cursor() as cur:
            cur.execute("SELECT * FROM actuators WHERE base_part_number = %s LIMIT 1;", (active_parts[0],))
            row = cur.fetchone()
        nxt = _next_size_part(row) if row else None
        return lookup(nxt or active_parts[0])
    return Decision(rule="uncertain")


def _supply_turn(res: Dict[str, Any], lang: str, visible_filters: Dict[str, Any], active_part_numbers: List[str],
                 make_debug, title) -> Tuple[Any, ...]:
    """Aclaración de alimentación de un código de tamaño: opciones REALES de la base; sin LLM, sin recomendaciones."""
    answer, ui_payload = acts.render_supply_clarification(res, lang)
    parts = list(active_part_numbers)
    debug_trace, cost = make_debug([], 0, [], parts)
    filters = {**visible_filters, "_pending": {"topic": "supply", "args": {"size_code": res["size"]}}}
    meta = {
        "intent": "clarify",
        "verification": {"status": "verified", "numbers_checked": 0, "ungrounded": []},
        "language": lang,
        "short_title": title(parts, visible_filters),
        "cost_usd": cost,
        "technical": True,
    }
    return answer, ui_payload, debug_trace, parts, filters, meta


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
    size_pending: Optional[Dict[str, Any]] = None     # «¿qué alimentación del 763B?»: la respuesta completa la referencia de tamaño
    if pending and pending.get("topic"):
        answered = resolve_clarification_answer(pending["topic"], user_query)
        if answered and pending["topic"] == "supply":
            size_pending = {**(pending.get("args") or {}), **answered}
        elif answered:
            pending_args = {**(pending.get("args") or {}), **answered}
    current_pending_args.set(pending_args)
    prev_idle = int(active_filters["_idle"]) if isinstance(active_filters.get("_idle"), (int, float)) else 0
    current_user_text.set(normalize_spoken_pn(" ".join(prev_users + [user_query]))[0])
    current_grounded_pns.get().update(pn_key(x) for x in active_part_numbers)
    for m in history_messages:                       # números mencionados antes en la misma sesión (usuario o asistente)
        current_grounded_pns.get().update(pn_key(x) for x in extract_part_numbers_from_text(str(m.get("content", ""))))
    visible_filters = {k: v for k, v in active_filters.items() if k not in ("_pending", "_idle")}

    cfg = load_llm_config()
    stats: Dict[str, int] = {"llm_retries": 0, "clf_in": 0, "clf_out": 0}

    def _debug(all_msgs, retries, traces, parts):
        prompt_tokens, completion_tokens = _usage(all_msgs)
        prompt_tokens += stats["clf_in"]
        completion_tokens += stats["clf_out"]
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
                "classifier_tokens": stats["clf_in"] + stats["clf_out"],
            },
            "active_context_part_numbers": parts,
            "tool_calls": traces,
            "steps": sorted(rec.steps, key=lambda s: s["start_ms"]),
            "cost_usd_estimate": cost,
            "language": lang,
        }, cost

    def _title(parts, filters):
        return make_short_title(parts, filters, lang, recommend=True)

    def _error_turn(code: str, detail: str):
        """Respuesta de error controlada: texto neutro al usuario; el detalle técnico va solo a debug_trace.error."""
        msg = render_alert_message(code, {}, lang)
        ui = {
            "display_type": "EDGE_CASE_ALERT",
            "actuators": [],
            "engineering_warnings": [msg],
            "alerts": [render_alert({"code": code, "params": {}}, lang)],
            "suggested_followups": [],
        }
        parts = list(active_part_numbers)
        dbg, cost = _debug([], 0, [], parts)
        dbg["error"] = detail[:300]
        meta = {
            "intent": "error",
            "verification": {"status": "fallback_template", "numbers_checked": 0, "ungrounded": []},
            "language": lang,
            "short_title": make_short_title(parts, visible_filters, lang),
            "cost_usd": cost,
            "technical": False,
        }
        return msg, ui, dbg, parts, visible_filters, meta

    def _neutral_reco_turn(all_msgs):
        """Recomendación sin criterios blandos: «Hay N modelos que cumplen X», orden neutro por torque y botones con torques reales."""
        ui_payload = build_ui_payload(list(current_turn_actuators.get().values()), lang, user_query)
        shown = ui_payload["actuators"]
        shown.sort(key=lambda r: ((_row_torque(r) if _row_torque(r) is not None else 0.0), r["base_part_number"]))
        recommendation, _extras = build_recommendation_payload(lang)
        if recommendation is not None:
            recommendation["ranking"] = []          # sin puntajes: la app no puede mostrar «% ajuste»
            ui_payload["recommendation"] = recommendation
        traces = list(current_turn_tool_traces.get())
        args = next((tr["arguments"] for tr in reversed(traces) if tr["tool_name"] == "recommend_actuators"), {}) or {}
        n = int(current_turn_recommendation.get().get("candidates") or len(shown))
        req = describe_requirements(args, lang)
        key = "reco_neutral_one" if n == 1 else ("reco_neutral" if req else "reco_neutral_all")
        answer = t_act(lang, key, n=n, req=req)
        ui_payload["suggested_followups"] = neutral_reco_followups(shown, args, lang)
        parts = [a["base_part_number"] for a in shown]
        filters = dict(visible_filters)
        filters.update(args)
        debug_trace, cost = _debug(all_msgs, 0, traces, parts)
        meta = {
            "intent": "recommend",
            "verification": {"status": "verified", "numbers_checked": 1, "ungrounded": []},   # el único número (N) sale de la base
            "language": lang,
            "short_title": make_short_title(parts, filters, lang, recommend=True),
            "cost_usd": cost,
            "technical": True,
        }
        return answer, ui_payload, debug_trace, parts, filters, meta

    def _data_turn(all_msgs):
        """catalog_overview / rank_actuators: texto determinista desde la salida SQL (sin LLM) + tarjetas del ranking."""
        traces = list(current_turn_tool_traces.get())
        out = traces[-1].get("raw_output") or {}
        answer = render_rank(out, lang) if traces[-1]["tool_name"] == "rank_actuators" else render_overview(out, lang)
        ui_payload = build_ui_payload(list(current_turn_actuators.get().values()), lang, user_query)
        if not re.search(r"csa|certif", user_query, re.I):      # avisos por modelo (p. ej. «sin CSA» ×4) que nadie pidió en un ranking/catálogo
            ui_payload["alerts"], ui_payload["engineering_warnings"] = [], []
        ui_payload["suggested_followups"] = acts.data_followups(lang, out.get("filters") if isinstance(out.get("filters"), dict) else None)
        shown = [a["base_part_number"] for a in ui_payload["actuators"]]
        parts = shown or list(active_part_numbers)
        debug_trace, cost = _debug(all_msgs, 0, traces, parts)
        ok = out.get("status") in ("RANKED", "CATALOG_OVERVIEW")
        meta = {
            "intent": derive_intent(traces, False),
            "verification": {"status": "verified", "numbers_checked": len(re.findall(r"\d+(?:\.\d+)?", answer)) if ok else 0, "ungrounded": []},
            "language": lang,
            "short_title": make_short_title(parts, visible_filters, lang) if shown else None,
            "cost_usd": cost,
            "technical": ok,
        }
        return answer, ui_payload, debug_trace, parts, _aged_filters(visible_filters, prev_idle) if visible_filters else {}, meta

    # ------------------------------------------------------------------ ROUTER determinista (sin LLM)
    r0 = time.perf_counter()
    decision: Optional[Decision] = None
    if ROUTER_ENABLED:
        try:
            known = _known_keys()
            decision = route(user_query, active_part_numbers, known, pending_args,
                             history_parts=_history_parts(history_messages, active_part_numbers, known), size_pending=size_pending)
        except Exception:  # noqa: BLE001  (una regla defectuosa nunca tumba el turno: cae al camino con LLM)
            decision = None
    if decision is not None and decision.kind == "resolve":     # referencias de tamaño / siguiente tamaño: se resuelven contra la base
        try:
            resolved = _resolve_decision(decision, active_part_numbers, lang)
        except Exception:  # noqa: BLE001  (base caída: cae al camino con LLM, que maneja el error)
            resolved = Decision(rule="uncertain")
        if isinstance(resolved, dict):                           # aclaración de alimentación (opciones reales de la base)
            rec.add_step("router", (r0 - t0) * 1000, (time.perf_counter() - r0) * 1000, detail=decision.rule)
            return _supply_turn(resolved, lang, visible_filters, active_part_numbers, _debug, _title)
        decision = resolved
    rec.add_step("router", (r0 - t0) * 1000, (time.perf_counter() - r0) * 1000, detail=decision.rule if decision else "disabled")
    if ROUTER_ENABLED and (decision is None or decision.kind == "none"):
        # Lo que las reglas no resuelven lo etiqueta un clasificador estructurado (un paso de LLM, JSON validado, sin redactar nada).
        # Si falla, el JSON es inválido o la confianza es baja: menú neutro con botones. No existe agente libre.
        c0 = time.perf_counter()
        base = decision if decision is not None else Decision(clean_query=user_query)
        known = _known_keys()
        clf_detail = "unclear"
        decision = None
        try:
            res, tin, tout = classifier.classify(
                base.clean_query or user_query, active_part_numbers, visible_filters,
                _classifier_invoke(stats, min(deadline, time.perf_counter() + CLASSIFIER_TIMEOUT_S + RETRY_BASE_S + 2.0)))
            stats["clf_in"], stats["clf_out"] = tin, tout
            if res is not None:
                decision = classifier.decision_from_classification(
                    res, base, user_query, active_part_numbers, _history_parts(history_messages, active_part_numbers, known), known)
                clf_detail = res.act if decision is not None else "unresolved"
        except Exception:  # noqa: BLE001
            decision = None
        if decision is None:
            decision = Decision(kind="reply", reply="unclear", rule="clf:unclear", act="unclear", clean_query=user_query)
        elif decision.kind == "resolve":
            try:
                resolved = _resolve_decision(decision, active_part_numbers, lang)
            except Exception:  # noqa: BLE001
                resolved = Decision(kind="reply", reply="unclear", rule="clf:unclear", act="unclear")
            if isinstance(resolved, dict):
                rec.add_step("classifier", (c0 - t0) * 1000, (time.perf_counter() - c0) * 1000, detail=clf_detail)
                return _supply_turn(resolved, lang, visible_filters, active_part_numbers, _debug, _title)
            decision = resolved
        rec.add_step("classifier", (c0 - t0) * 1000, (time.perf_counter() - c0) * 1000, detail=clf_detail)
    if decision is not None and decision.kind == "reply":
        return _reply_turn(decision, lang, visible_filters, active_part_numbers, _debug, _title, prev_idle)
    llm_query = decision.clean_query if decision is not None and (decision.injection or decision.normalized) else user_query

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

    run_cfg = {"callbacks": [rec]}
    retry_cfg = {"callbacks": [rec]}

    llm_failed = False
    inner = None
    all_msgs: List[BaseMessage] = []
    try:
        pre_msgs = lc_messages
        if decision is not None and decision.kind == "tools":   # las herramientas del router corren SIN LLM, antes de construirlo
            pre_msgs = build_router_graph(decision).invoke({"messages": lc_messages}, config={"callbacks": [rec]})["messages"]
        if decision is not None and decision.kind == "tools" and current_turn_tool_traces.get() \
                and current_turn_tool_traces.get()[-1]["tool_name"] in DATA_TOOLS:
            return _data_turn(pre_msgs)
        if current_turn_clarification.get() or (decision is not None and decision.kind == "tools" and _neutral_reco()):
            all_msgs = pre_msgs                        # la pregunta de aclaración / el texto sin criterios blandos los arma la app, sin LLM
        else:
            try:
                inner = create_react_agent(build_llm(), LLM_TOOLS)
            except Exception as exc:  # noqa: BLE001  (p. ej. sin clave): mismo manejo que un LLM caído
                raise LLMUnavailable(f"{type(exc).__name__}: {str(exc)[:120]}") from exc
            result_state = invoke_with_retry(inner, {"messages": pre_msgs}, run_cfg, stats, deadline)
            all_msgs = result_state["messages"]
    except LLMUnavailable as exc:
        llm_failed = True
        if not current_turn_tool_traces.get() and not current_turn_clarification.get():
            return _error_turn("LLM_UNAVAILABLE", str(exc))
    except Exception as exc:  # noqa: BLE001  (fallo inesperado del grafo/herramientas: respuesta controlada, detalle solo en debug)
        if not current_turn_tool_traces.get() and not current_turn_clarification.get():
            return _error_turn("SERVICE_UNAVAILABLE", f"{type(exc).__name__}: {str(exc)[:200]}")
        llm_failed = True

    # ------------------------------------------------------------------ ACLARACIÓN (pregunta del asistente, sin LLM)
    if current_turn_clarification.get():
        return _clarification_turn(current_turn_clarification.get(), lang, visible_filters, active_part_numbers,
                                   all_msgs, 0, _debug, _title)

    if _neutral_reco():
        return _neutral_reco_turn(all_msgs)

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
    elif len(answer.split()) > (MAX_ANSWER_WORDS if has_cards else MAX_NOCARD_WORDS + 20):
        template_reason = "too_long"          # una "frase" larga sin puntos que el recorte no puede partir
    elif has_cards and _typo_without_suggestion(answer):
        template_reason = "too_long"          # dice "no existe" pero no nombra el modelo cercano que muestra la tarjeta: plantilla
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
                    inner, {"messages": all_msgs + [HumanMessage(content=feedback)]}, retry_cfg, stats, deadline)
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

    if verifier_error and re.search(r"\d", answer):
        # sin base de datos no se puede comprobar ninguna cifra (REGLA 4): nunca se muestra texto del LLM con números sin verificar
        return _error_turn("SERVICE_UNAVAILABLE", "verifier unavailable (database error)")
    status = "unverified" if verifier_error else "verified"
    ui_t = time.perf_counter()
    if decision is not None and decision.oos_note:
        current_turn_alerts.get().append({"code": "OUT_OF_SCOPE", "params": {}})
    ui_payload = build_ui_payload(list(current_turn_actuators.get().values()), lang, user_query)
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
            query=user_query,
            compare=sum(1 for tr in traces if isinstance(tr.get("raw_output"), dict)
                        and tr["raw_output"].get("status") == "EXACT_MATCH") >= 2,
        )
        if llm_failed and traces:   # modo degradado: respuesta correcta desde la base, con aviso informativo (no error)
            ui_payload["alerts"].append(render_degraded_alert(lang))
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

    # Higiene de estado: los filtros solo viven mientras la conversación sigue recomendando; una ficha, un concepto o una
    # comparación los hacen caducar (no se arrastran a «¿en qué puedes ayudarme?» ni a la siguiente consulta no relacionada).
    used_reco = any(tr["tool_name"] == "recommend_actuators" and tr.get("arguments") for tr in traces)
    updated_filters = dict(visible_filters) if used_reco else {}
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
        "technical": bool(traces),
    }
    return answer, ui_payload, debug_trace, updated_parts, updated_filters, meta
