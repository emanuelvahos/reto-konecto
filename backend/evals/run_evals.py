try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import os
import sys
import io
import time
import argparse
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional
from dotenv import load_dotenv

# Configurar encoding UTF-8 seguro para consolas Windows (evita UnicodeEncodeError con emojis)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Asegurar que el directorio 'backend' esté en sys.path para imports de app.*
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

ROOT_DIR = BACKEND_DIR.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")

import httpx
from fastapi.testclient import TestClient
from app.main import app
from app.config import load_llm_config
sys.path.insert(0, str(Path(__file__).resolve().parent))
from oracle_check import BY_PN, GOLDEN, oracle_value, oracle_verify, states_value, ui_matches_oracle  # noqa: E402

REPORT_PATH = Path(__file__).resolve().parent / "EVALUATION_REPORT.md"


class EvalClient:
    """Wrapper unificado que permite ejecutar las pruebas con FastAPI TestClient (en proceso)

    o contra una instancia HTTP viva (Docker / Cloud en http://localhost:8001).
    """

    def __init__(self, base_url: Optional[str] = None, auth_token: Optional[str] = None):
        self.base_url = base_url.rstrip("/") if base_url else None
        self.auth_token = auth_token
        if self.base_url:
            self._httpx = httpx.Client(base_url=self.base_url, timeout=90.0)
            self._test_client = None
        else:
            self._httpx = None
            self._test_client = TestClient(app)

    def post(self, path: str, json: Dict[str, Any], headers: Optional[Dict[str, str]] = None):
        h = headers.copy() if headers else {}
        if self.auth_token and "Authorization" not in h:
            h["Authorization"] = f"Bearer {self.auth_token}"
        if self._httpx:
            return self._httpx.post(path, json=json, headers=h)
        return self._test_client.post(path, json=json, headers=h)

    def login(self, email: str = "engineer@konecto.io", password: str = "Konecto2026!") -> Optional[str]:
        r = self.post("/api/auth/login", json={"email": email, "password": password})
        if r.status_code == 200:
            token = r.json().get("token") or r.json().get("access_token")
            self.auth_token = token
            return token
        return None


class EvalScenario:
    def __init__(
        self,
        scenario_id: str,
        category: str,
        title: str,
        turns: List[Any],
        validator: Callable[[List[Dict[str, Any]]], None],
    ):
        """turns: textos, o funciones f(respuestas_previas) -> texto (p. ej. elegir una opción de aclaración)."""
        self.scenario_id = scenario_id
        self.category = category
        self.title = title
        self.turns = turns
        self.validator = validator


def _opt_value(label_part: str) -> Callable[[List[Dict[str, Any]]], str]:
    """Turno que reenvía el `value` de la opción de la aclaración previa cuyo value contiene label_part."""
    def pick(prev: List[Dict[str, Any]]) -> str:
        opts = (prev[-1].get("ui_payload") or {}).get("clarification", {}).get("options") or []
        for o in opts:
            if label_part.lower() in o["value"].lower():
                return o["value"]
        raise AssertionError(f"la aclaración no ofreció una opción con '{label_part}': {opts}")
    return pick


def assert_oracle_clean(resp_json: Dict[str, Any]) -> None:
    """Todo turno: cifras con unidad y fila correctas según el ORÁCULO, tarjetas == oráculo, sin Markdown."""
    res = oracle_verify(resp_json, resp_json.get("_query", ""))
    assert res.ok, f"cifras fuera del oráculo (unidad/fila): {res.ungrounded} en {resp_json.get('answer', '')[:200]!r}"
    diffs = ui_matches_oracle(resp_json)
    assert not diffs, f"ui_payload difiere del oráculo: {diffs[:3]}"
    assert "**" not in resp_json.get("answer", "") and "\n#" not in resp_json.get("answer", ""), "la respuesta trae Markdown"


def assert_states(resp_json: Dict[str, Any], pn: str, *fields: str) -> None:
    for f in fields:
        v = oracle_value(pn, f)
        assert v is not None and states_value(resp_json.get("answer", ""), v), (
            f"la respuesta debía decir {pn}.{f}={v:g} (oráculo): {resp_json.get('answer', '')[:200]!r}"
        )


def assert_alert(resp_json: Dict[str, Any], *codes: str) -> None:
    have = {a["code"] for a in (resp_json.get("ui_payload") or {}).get("alerts") or []}
    assert set(codes) & have, f"se esperaba alguna alerta de {codes}, hay {sorted(have)}"


def assert_alert_message_has(resp_json: Dict[str, Any], code: str, needle: str) -> None:
    msgs = [a["message"] for a in (resp_json.get("ui_payload") or {}).get("alerts") or [] if a["code"] == code]
    assert any(needle in m for m in msgs), f"la alerta {code} debía contener '{needle}' (oráculo): {msgs}"


def assert_tool_status(resp_json: Dict[str, Any], *statuses: str) -> None:
    got = [tc["raw_output"].get("status") for tc in (resp_json.get("debug_trace") or {}).get("tool_calls") or []
           if isinstance(tc.get("raw_output"), dict)]
    assert set(statuses) & set(got), f"estado de herramienta {got}, esperado alguno de {statuses}"


def assert_intent(resp_json: Dict[str, Any], *intents: str) -> None:
    assert resp_json.get("intent") in intents, f"intent={resp_json.get('intent')!r}, esperado {intents}"


def assert_ui_parts_all(resp_json: Dict[str, Any], pred) -> None:
    parts = (resp_json.get("ui_payload") or {}).get("actuators") or []
    assert parts, "ui_payload.actuators vacío"
    bad = [a["base_part_number"] for a in parts if not pred(BY_PN[a["base_part_number"]])]
    assert not bad, f"tarjetas que incumplen la restricción dura (según oráculo): {bad}"


def assert_display(resp_json: Dict[str, Any], display_type: str) -> None:
    got = (resp_json.get("ui_payload") or {}).get("display_type")
    assert got == display_type, f"display_type={got!r}, esperado {display_type!r}"


def assert_options_between(resp_json: Dict[str, Any], lo: int, hi: int) -> None:
    n = len(((resp_json.get("ui_payload") or {}).get("clarification") or {}).get("options") or [])
    assert lo <= n <= hi, f"opciones={n}, esperado {lo}-{hi}"


def _oracle_max(pred) -> float:
    return max(max(r["on_off_torque_nm"] or 0, r["modulating_torque_nm"] or 0) for r in GOLDEN if r["is_available"] and pred(r))


def build_scenarios() -> List[EvalScenario]:
    P764A = "764A00-11320000/A"
    return [
        # 1. Exact Part Number Retrieval (110V Weatherproof): la ficha completa va en la tarjeta; el texto es corto
        EvalScenario(
            "EVAL-01", "Specific Data Retrieval", "Exact lookup of 763B00-11300000/A (110V 1-Phase Weatherproof)",
            ["What are the full technical specifications for part number 763B00-11300000/A?"],
            lambda res: (
                assert_oracle_clean(res[-1]),
                assert_ui_has_part(res[-1], "763B00-11300000/A"),
                assert_intent(res[-1], "lookup"),
                assert_tool_called(res[-1], "lookup_actuator_by_part_number"),
            ),
        ),
        # 2. Multi-Turn Coreference Resolution (valores esperados leídos del oráculo)
        EvalScenario(
            "EVAL-02", "Multi-Turn Coreference", f"3-turn follow-up on {P764A} resolving 'it' across turns",
            [
                f"Give me the torque specs for {P764A}.",
                "And how much motor power in Watts does it draw?",
                "What is its operating speed and FLA at 50Hz?",
            ],
            lambda res: (
                [assert_oracle_clean(r) for r in res],
                assert_states(res[0], P764A, "on_off_torque_nm", "modulating_torque_nm"),
                assert_states(res[1], P764A, "motor_power_watts"),
                assert_states(res[2], P764A, "speed_50hz_sec", "fla_50hz_amps"),
            ),
        ),
        # 3. 220V 3-Phase column order (60 Hz | 50 Hz): oráculo
        EvalScenario(
            "EVAL-03", "Specific Data Retrieval", "Lookup 763A00-11330C00/A (220V 3-Phase speed 50Hz vs 60Hz)",
            ["For part number 763A00-11330C00/A, what is the operating speed at 50Hz and at 60Hz?"],
            lambda res: (assert_oracle_clean(res[-1]), assert_states(res[-1], "763A00-11330C00/A", "speed_50hz_sec", "speed_60hz_sec")),
        ),
        # 4. Edge Case: Model Explicitly Listed as N/A in 220V 3-Phase
        EvalScenario(
            "EVAL-04", "Edge Case: N/A Model", "Querying 761A00-11330C00/A which is N/A in 220V 3-Phase table",
            ["Can I get the specs for 761A00-11330C00/A?"],
            lambda res: (
                assert_oracle_clean(res[-1]),
                assert_tool_status(res[-1], "MODEL_LISTED_AS_NA"),
                assert_alert(res[-1], "MODEL_LISTED_AS_NA"),
                assert_any_in_answer(res[-1], ["n/a", "not available", "single phase", "110v", "220v", "not offered", "unsupported", "listed"]),
            ),
        ),
        # 5. Edge Case: OCR / User Typo Fuzzy Recovery (761800 -> 761B00)
        EvalScenario(
            "EVAL-05", "Edge Case: Typo Fuzzy Match", "Querying corrupted part number 761800-11300000/A (8 instead of B)",
            ["What is the torque of actuator 761800-11300000/A?"],
            lambda res: (
                assert_oracle_clean(res[-1]),
                assert_tool_status(res[-1], "TYPO_OR_CLOSEST_MATCH_FOUND"),
                assert_any_in_answer(res[-1], ["761b00-11300000/a", "761a00-11300000/a", "did you mean", "closest", "similar"]),
            ),
        ),
        # 6. Edge Case: Completely Invalid Part Number
        EvalScenario(
            "EVAL-06", "Edge Case: Invalid Part Number", "Querying non-existent part number 999Z99-00000000/Z",
            ["Give me the FLA current for part number 999Z99-00000000/Z."],
            lambda res: (
                assert_tool_status(res[-1], "INVALID_PART_NUMBER"),
                assert_any_in_answer(res[-1], ["not", "no ", "invalid", "does not exist", "found", "unable"]),
                assert_oracle_clean(res[-1]),
            ),
        ),
        # 7. Product Recommendation: Explosionproof 24V DC Modulating (todos los datos presentes: no pregunta)
        EvalScenario(
            "EVAL-07", "Product Recommendation", "Recommend Explosionproof actuator with >= 200 Nm Modulating torque on 24V DC",
            ["I need an Explosionproof actuator for a modulating valve requiring at least 200 Nm on 24V DC."],
            lambda res: (
                assert_oracle_clean(res[-1]),
                assert_intent(res[-1], "recommend"),
                assert_ui_has_part(res[-1], "763X30-11370000/A"),
                assert_ui_parts_all(res[-1], lambda r: r["enclosure_type"] == "Explosionproof" and r["voltage_num"] == 24),
            ),
        ),
        # 8. Edge Case: CSA Certification Exception on Sizes 6 & 7 (techo de torque CSA tomado del oráculo)
        EvalScenario(
            "EVAL-08", "Edge Case: CSA Footnote Trap", "Requesting 6,000 Nm actuator with mandatory CSA Certification",
            ["Recommend an actuator that delivers at least 6,000 Nm of torque and MUST be CSA certified."],
            lambda res: (
                assert_oracle_clean(res[-1]),
                assert_intent(res[-1], "recommend"),
                assert_alert(res[-1], "CSA_SIZE_LIMIT", "CSA_NOT_CERTIFIED"),
                assert_alert_message_has(res[-1], "TORQUE_ABOVE_CEILING", f"{_oracle_max(lambda r: r['csa_certified']):g} Nm"),
            ),
        ),
        # 9. Edge Case: Impossible Requirements -> Constraint Relaxation (techo 24V del oráculo; la dura no se relaja)
        EvalScenario(
            "EVAL-09", "Edge Case: Impossible Requirement", "Requesting 1,500 Nm actuator running on 24V DC power supply",
            ["Which 24V DC Series 76 actuator can provide 1,500 Nm of torque?"],
            lambda res: (
                assert_oracle_clean(res[-1]),
                assert_intent(res[-1], "recommend"),
                assert_alert_message_has(res[-1], "TORQUE_ABOVE_CEILING", f"{_oracle_max(lambda r: r['voltage_num'] == 24):g} Nm"),
                assert_ui_parts_all(res[-1], lambda r: r["voltage_num"] == 24),
            ),
        ),
        # 10. Ambiguous Query: falta On/Off vs Modulating -> aclaración real, luego se resuelve en el mismo contexto
        EvalScenario(
            "EVAL-10", "Edge Case: Ambiguous Service Type", "110V Explosionproof 450 Nm without service type: clarify, then resolve",
            ["I need a 110V Single Phase Explosionproof actuator for 450 Nm torque.", _opt_value("modulating")],
            lambda res: (
                assert_intent(res[0], "clarify"),
                assert_display(res[0], "CLARIFICATION"),
                assert_options_between(res[0], 2, 4),
                assert_oracle_clean(res[-1]),
                assert_intent(res[-1], "recommend"),
                assert_ui_parts_all(
                    res[-1],
                    lambda r: r["enclosure_type"] == "Explosionproof" and r["voltage_num"] == 110 and (r["modulating_torque_nm"] or 0) >= 450,
                ),
            ),
        ),
        # 11. Semantic Knowledge & Footnote Tolerance Calculation (+/-10% Voltage)
        EvalScenario(
            "EVAL-11", "Engineering Rules & Knowledge", "Checking allowable voltage tolerance (+/-10%) and hazardous location ratings",
            ["What is the allowable motor voltage tolerance for Series 76 actuators, and what hazardous area certifications do Explosionproof models have?"],
            lambda res: (
                assert_intent(res[-1], "knowledge"),
                assert_any_in_answer(res[-1], ["10%", "+/-10", "+/- 10", "class i", "ex d iib t4", "atex", "iecex"]),
            ),
        ),
    ]


def _norm_answer(text: str) -> str:
    """Minúsculas, sin comas y con guiones/espacios Unicode (U+2010..2015, U+2212, NBSP) normalizados."""
    for ch in "‐‑‒–—―−":
        text = text.replace(ch, "-")
    for ch in "   ":
        text = text.replace(ch, " ")
    return text.lower().replace(",", "")


def assert_in_answer(resp_json: Dict[str, Any], expected_substrings: List[str]) -> None:
    ans = _norm_answer(resp_json.get("answer", ""))
    for sub in expected_substrings:
        clean_sub = sub.lower().replace(",", "")
        assert clean_sub in ans, f"Expected '{sub}' in answer, got: {resp_json.get('answer', '')[:250]}"


def assert_any_in_answer(resp_json: Dict[str, Any], candidates: List[str]) -> None:
    ans = _norm_answer(resp_json.get("answer", ""))
    assert any(c.lower().replace(",", "") in ans for c in candidates), (
        f"Expected at least one of {candidates} in answer, got: {resp_json.get('answer', '')[:250]}"
    )


def assert_ui_has_part(resp_json: Dict[str, Any], part_number: str) -> None:
    ui = resp_json.get("ui_payload") or {}
    actuators = ui.get("actuators") or []
    parts = [a["base_part_number"] for a in actuators if "base_part_number" in a]
    assert part_number in parts, f"Expected {part_number} in ui_payload.actuators, got {parts}"


def assert_tool_called(resp_json: Dict[str, Any], tool_name: str) -> None:
    trace = resp_json.get("debug_trace") or {}
    calls = [t["tool_name"] for t in trace.get("tool_calls") or [] if "tool_name" in t]
    assert tool_name in calls, f"Expected tool {tool_name} to be called, got {calls}"


def run_evaluation_suite(
    client: Optional[EvalClient] = None,
    scenario_filter: Optional[str] = None,
    verbose: bool = False,
) -> int:
    if client is None:
        client = EvalClient()

    all_scenarios = build_scenarios()
    scenarios = [s for s in all_scenarios if scenario_filter is None or s.scenario_id.lower() == scenario_filter.lower()]
    if not scenarios:
        print(f"⚠️ No scenarios matched filter '{scenario_filter}'. Available: {[s.scenario_id for s in all_scenarios]}")
        return 1

    llm_cfg = load_llm_config()
    chat_model = llm_cfg.chat_model
    server_mode = client.base_url if client.base_url else "In-Process TestClient"

    results_md = [
        "# Konecto Series 76 Assistant — Automated Evaluation Report",
        "",
        f"- **Model Configured:** `{chat_model}`",
        f"- **Provider:** `{llm_cfg.provider}`",
        f"- **Evaluation Client:** `{server_mode}`",
        f"- **Total Scenarios:** `{len(scenarios)}`",
        f"- **Execution Timestamp:** `{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}`",
        "",
        "| ID | Category | Scenario | Turns | Latency (ms) | Tools Invoked | Status |",
        "|---|---|---|---|---|---|---|",
    ]

    print("\n" + "=" * 70)
    print(f"🚀 RUNNING KONECTO SERIES 76 EVALUATION SUITE ({len(scenarios)} Scenarios)")
    print(f"   Target: {server_mode}")
    print(f"   Model:  {chat_model}")
    print("=" * 70 + "\n")

    passed = 0
    for sc in scenarios:
        t0 = time.perf_counter()
        session_id = None
        turn_responses: List[Dict[str, Any]] = []
        tools_used: List[str] = []

        try:
            for q in sc.turns:
                q = q(turn_responses) if callable(q) else q
                payload = {"query": q}
                if session_id:
                    payload["session_id"] = session_id
                r = client.post("/api/conversation", json=payload)
                assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
                data = r.json()
                data["_query"] = q
                session_id = data["session_id"]
                turn_responses.append(data)
                for tc in (data.get("debug_trace") or {}).get("tool_calls") or []:
                    if "tool_name" in tc:
                        tools_used.append(tc["tool_name"])

            sc.validator(turn_responses)
            elapsed = round((time.perf_counter() - t0) * 1000)
            passed += 1
            status_str = "✅ PASS"
            print(f"[PASS] {sc.scenario_id} ({elapsed} ms): {sc.title}")
            if verbose:
                print(f"       Answer: {turn_responses[-1].get('answer', '')[:140]}...")
                print(f"       Tools:  {list(dict.fromkeys(tools_used))}")
        except Exception as e:
            elapsed = round((time.perf_counter() - t0) * 1000)
            if verbose:
                import traceback
                traceback.print_exc()
            status_str = f"❌ FAIL ({str(e)[:60]})"
            print(f"[FAIL] {sc.scenario_id} ({elapsed} ms): {sc.title}")
            print(f"       Error: {e}")

        tools_str = ", ".join(dict.fromkeys(tools_used)) if tools_used else "None"
        results_md.append(
            f"| `{sc.scenario_id}` | {sc.category} | {sc.title} | {len(sc.turns)} | {elapsed} | `{tools_str}` | {status_str} |"
        )

    pass_pct = round(passed * 100 / len(scenarios), 1)
    results_md.extend(
        [
            "",
            f"## Summary: **{passed}/{len(scenarios)} Scenarios Passed ({pass_pct}%)**",
        ]
    )
    REPORT_PATH.write_text("\n".join(results_md), encoding="utf-8")
    print("\n" + "=" * 70)
    print(f"📊 EVALUATION COMPLETE: {passed}/{len(scenarios)} Passed ({pass_pct}%)")
    print(f"📄 Report written to {REPORT_PATH}")
    print("=" * 70 + "\n")

    return 0 if passed == len(scenarios) else 1


# =====================================================================
# PYTEST INTEGRATION (Para que pytest backend/evals/run_evals.py funcione)
# =====================================================================
import pytest

@pytest.mark.parametrize("sc", build_scenarios(), ids=[s.scenario_id for s in build_scenarios()])
def test_evaluation_scenario(sc: EvalScenario):
    client = EvalClient()
    session_id = None
    turn_responses: List[Dict[str, Any]] = []

    for q in sc.turns:
        q = q(turn_responses) if callable(q) else q
        payload = {"query": q}
        if session_id:
            payload["session_id"] = session_id
        r = client.post("/api/conversation", json=payload)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        data = r.json()
        data["_query"] = q
        session_id = data["session_id"]
        turn_responses.append(data)

    sc.validator(turn_responses)


def main():
    parser = argparse.ArgumentParser(description="Konecto Series 76 Evals Benchmark Runner")
    parser.add_argument("--scenario", "-s", type=str, default=None, help="Filter by scenario ID (e.g. EVAL-01)")
    parser.add_argument("--live", action="store_true", help="Run against live server at http://localhost:8001")
    parser.add_argument("--base-url", type=str, default=None, help="Custom live server base URL")
    parser.add_argument("--auth", action="store_true", help="Login with engineer@konecto.io before running")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print detailed tool calls and answers")

    args = parser.parse_args()

    base_url = args.base_url
    if args.live and not base_url:
        base_url = "http://localhost:8001"

    client = EvalClient(base_url=base_url)
    if args.auth:
        token = client.login()
        if token:
            print("🔑 Logged in successfully with engineer@konecto.io")
        else:
            print("⚠️ Failed to login with engineer@konecto.io, continuing unauthenticated")

    code = run_evaluation_suite(
        client=client,
        scenario_filter=args.scenario,
        verbose=args.verbose,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
