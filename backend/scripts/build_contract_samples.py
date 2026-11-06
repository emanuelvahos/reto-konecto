"""Regenera backend/evals/fixtures/contract_v2_samples.json con respuestas REALES del pipeline (sin LLM).

Cada muestra sale de POST /api/conversation (TestClient en proceso): router determinista -> herramientas reales -> ui_payload
construido desde PostgreSQL. El único sustituto es el redactor del LLM, que aquí devuelve la frase determinista
(`build_fallback_answer`) calculada desde las filas del turno; así no hay ninguna cifra inventada.

Uso (con la base poblada):  python scripts/build_contract_samples.py
"""
import json
import sys
from pathlib import Path

from langchain_core.messages import AIMessage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.agent as agent  # noqa: E402
from app.fallback import build_fallback_answer, infer_groups  # noqa: E402
from app.i18n import detect_language, render_alert_message  # noqa: E402
from app.tools import current_turn_actuators, current_turn_alerts, current_turn_tool_traces, fetch_ui_actuators  # noqa: E402

OUT = ROOT / "evals" / "fixtures" / "contract_v2_samples.json"
FIXED_SESSION = "00000000-0000-4000-8000-000000000076"


class Writer:
    """Sustituto determinista del modelo: redacta la frase corta desde las filas ya obtenidas por las herramientas."""

    def __init__(self, query, locale, fail=False):
        self.query, self.locale, self.fail = query, locale, fail

    def invoke(self, state, config=None):
        if self.fail:
            raise ConnectionError("simulated outage")
        lang = detect_language(self.query, self.locale, [])
        traces = current_turn_tool_traces.get()
        rows = fetch_ui_actuators(list(current_turn_actuators.get()))
        alerts = [render_alert_message(a["code"], a.get("params"), lang) for a in current_turn_alerts.get()]
        text = build_fallback_answer(
            lang, rows, alerts, [t.get("raw_output") for t in traces],
            groups=infer_groups(self.query), recommend=bool(traces) and traces[-1]["tool_name"] == "recommend_actuators",
        )
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        return {"messages": list(state["messages"]) + [AIMessage(content=text, usage_metadata=usage)]}


# nombre -> (consulta, locale, el redactor falla). Los 4 primeros conservan el nombre que ya usa la app.
SAMPLES = {
    "single_spec_card": ("¿Cuánto torque y qué potencia tiene el 763B00-11300000/A?", "es", False),
    "comparison_table": ("Compara la velocidad del 763B00-11300000/A y del 763A00-11300000/A", "es", False),
    "recommendation_with_relaxation": ("Necesito un actuador Explosionproof de 24V on/off de al menos 50 Nm que gire 90° en menos de 2 segundos", "es", False),
    "clarification": ("Necesito un actuador de 450 Nm", "es", False),
    "comparison_table_3": ("Compare the torque of 761A00-11300000/A, 762A00-11300000/A and 763A00-11300000/A", "en", False),
    "three_phase_single_torque": ("¿Qué torque tiene el 763A00-11330C00/A?", "es", False),
    "model_listed_as_na": ("Dame las especificaciones del 761A00-11330C00/A", "es", False),
    "recommendation_no_match": ("Quiero un actuador de 24V weatherproof", "es", False),
    "out_of_scope": ("¿Cuánto cuesta el 763B00-11300000/A y cuál es el plazo de entrega?", "es", False),
    "llm_error": ("hola, necesito ayuda con un actuador", "es", True),
    "degraded_lookup": ("¿Cuánto torque y qué potencia tiene el 763B00-11300000/A?", "es", True),
    "typo_correction": ("Give me the specs of 761800-11300000/A", "en", False),
}


def build() -> dict:
    from fastapi.testclient import TestClient

    from app.main import app

    out = {}
    orig_create, orig_llm, orig_sleep, orig_base = agent.create_react_agent, agent.build_llm, agent._sleep, agent.RETRY_BASE_S
    agent.build_llm = lambda: None
    agent._sleep = lambda s: None
    agent.RETRY_BASE_S = 0.0
    try:
        with TestClient(app) as client:
            for name, (query, locale, fail) in SAMPLES.items():
                agent.create_react_agent = lambda llm, tools, q=query, l=locale, f=fail: Writer(q, l, f)
                r = client.post("/api/conversation", json={"query": query, "locale": locale})
                r.raise_for_status()
                body = r.json()
                body["session_id"] = FIXED_SESSION
                out[name] = body
    finally:
        agent.create_react_agent, agent.build_llm, agent._sleep, agent.RETRY_BASE_S = orig_create, orig_llm, orig_sleep, orig_base
    return out


if __name__ == "__main__":
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for k, v in data.items():
        print(f"{k:34s} {v['ui_payload']['display_type']:20s} intent={v['intent']:9s} actuators={len(v['ui_payload']['actuators'])} | {v['answer'][:70]}")
