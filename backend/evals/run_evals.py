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
        turns: List[str],
        validator: Callable[[List[Dict[str, Any]]], None],
    ):
        self.scenario_id = scenario_id
        self.category = category
        self.title = title
        self.turns = turns
        self.validator = validator


def build_scenarios() -> List[EvalScenario]:
    return [
        # 1. Exact Part Number Retrieval (110V Weatherproof)
        EvalScenario(
            "EVAL-01",
            "Specific Data Retrieval",
            "Exact lookup of 763B00-11300000/A (110V 1-Phase Weatherproof)",
            ["What are the full technical specifications for part number 763B00-11300000/A?"],
            lambda res: (
                assert_in_answer(res[-1], ["500", "380", "90"]),
                assert_ui_has_part(res[-1], "763B00-11300000/A"),
            ),
        ),
        # 2. Multi-Turn Coreference Resolution (Follow-up without repeating part number)
        EvalScenario(
            "EVAL-02",
            "Multi-Turn Coreference",
            "3-turn follow-up on 764A00-11320000/A resolving 'it' across turns",
            [
                "Give me the torque specs for 764A00-11320000/A.",
                "And how much motor power in Watts does it draw?",
                "What is its operating speed and FLA at 50Hz?",
            ],
            lambda res: (
                assert_in_answer(res[0], ["750", "680"]),
                assert_in_answer(res[1], ["90"]),
                assert_in_answer(res[2], ["27", "3.2"]),
            ),
        ),
        # 3. 220V 3-Phase Inverted Columns Verification
        EvalScenario(
            "EVAL-03",
            "Specific Data Retrieval",
            "Lookup 763A00-11330000/A (220V 3-Phase speed 50Hz vs 60Hz)",
            ["For part number 763A00-11330000/A, what is the operating speed at 50Hz and at 60Hz?"],
            lambda res: assert_in_answer(res[-1], ["32", "26"]),
        ),
        # 4. Edge Case: Model Explicitly Listed as N/A in 220V 3-Phase
        EvalScenario(
            "EVAL-04",
            "Edge Case: N/A Model",
            "Querying 761A00-11330000/A which is N/A in 220V 3-Phase table",
            ["Can I get the specs for 761A00-11330000/A?"],
            lambda res: (
                assert_any_in_answer(res[-1], ["n/a", "not available", "single phase", "110v", "220v", "not offered", "unsupported"]),
                assert_tool_called(res[-1], "lookup_actuator_by_part_number"),
            ),
        ),
        # 5. Edge Case: OCR / User Typo Fuzzy Recovery (761800 -> 761B00)
        EvalScenario(
            "EVAL-05",
            "Edge Case: Typo Fuzzy Match",
            "Querying corrupted part number 761800-11300000/A (8 instead of B)",
            ["What is the torque of actuator 761800-11300000/A?"],
            lambda res: (
                assert_any_in_answer(res[-1], ["761b00-11300000/a", "761a00-11300000/a", "did you mean", "fuzzy", "suggested"]),
                assert_tool_called(res[-1], "lookup_actuator_by_part_number"),
            ),
        ),
        # 6. Edge Case: Completely Invalid Part Number
        EvalScenario(
            "EVAL-06",
            "Edge Case: Invalid Part Number",
            "Querying non-existent part number 999Z99-00000000/Z",
            ["Give me the FLA current for part number 999Z99-00000000/Z."],
            lambda res: assert_any_in_answer(res[-1], ["not", "no ", "invalid", "does not exist", "found", "unable"]),
        ),
        # 7. Product Recommendation: Explosionproof 24V DC Modulating
        EvalScenario(
            "EVAL-07",
            "Product Recommendation",
            "Recommend Explosionproof actuator with >= 200 Nm Modulating torque on 24V DC",
            ["I need an Explosionproof actuator for a modulating valve requiring at least 200 Nm on 24V DC."],
            lambda res: (
                assert_any_in_answer(res[-1], ["763X30-11370000/A", "763x", "220"]),
                assert_ui_has_part(res[-1], "763X30-11370000/A"),
            ),
        ),
        # 8. Edge Case: CSA Certification Exception on Sizes 6 & 7
        EvalScenario(
            "EVAL-08",
            "Edge Case: CSA Footnote Trap",
            "Requesting 6,000 Nm actuator with mandatory CSA Certification",
            ["Recommend an actuator that delivers at least 6,000 Nm of torque and MUST be CSA certified."],
            lambda res: assert_any_in_answer(res[-1], ["not csa", "sizes 6 and 7", "size 6", "size 7", "3,000", "3000", "ce only", "ce"]),
        ),
        # 9. Edge Case: Impossible Requirements -> Constraint Relaxation
        EvalScenario(
            "EVAL-09",
            "Edge Case: Impossible Requirement",
            "Requesting 1,500 Nm actuator running on 24V DC power supply",
            ["Which 24V DC Series 76 actuator can provide 1,500 Nm of torque?"],
            lambda res: assert_any_in_answer(res[-1], ["240", "220", "110v", "220v", "no ", "not available", "maximum", "cannot"]),
        ),
        # 10. Edge Case: Ambiguous Query (Torque requested without specifying On/Off vs Modulating)
        EvalScenario(
            "EVAL-10",
            "Edge Case: Ambiguous Service Type",
            "Requesting 450 Nm in 110V Explosionproof without specifying On/Off vs Modulating",
            ["I need a 110V Single Phase Explosionproof actuator for 450 Nm torque."],
            lambda res: assert_any_in_answer(res[-1], ["763y30-11300000/a", "764x30-11300000/a", "on/off", "modulating", "763y", "764x"]),
        ),
        # 11. Semantic Knowledge & Footnote Tolerance Calculation (+/-10% Voltage)
        EvalScenario(
            "EVAL-11",
            "Engineering Rules & RAG",
            "Checking allowable voltage tolerance (+/-10%) and hazardous location ratings",
            ["What is the allowable motor voltage tolerance for Series 76 actuators, and what hazardous area certifications do Explosionproof models have?"],
            lambda res: assert_any_in_answer(res[-1], ["10%", "+/-10", "+/- 10", "class i", "ex d iib t4", "atex", "iecex"]),
        ),
    ]


def assert_in_answer(resp_json: Dict[str, Any], expected_substrings: List[str]) -> None:
    ans = resp_json.get("answer", "").lower().replace(",", "")
    for sub in expected_substrings:
        clean_sub = sub.lower().replace(",", "")
        assert clean_sub in ans, f"Expected '{sub}' in answer, got: {resp_json.get('answer', '')[:250]}"


def assert_any_in_answer(resp_json: Dict[str, Any], candidates: List[str]) -> None:
    ans = resp_json.get("answer", "").lower().replace(",", "")
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

    chat_model = os.getenv("LLM_CHAT_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
    embed_model = os.getenv("EMBEDDING_MODEL", "nvidia/nemotron-3-embed-1b")
    server_mode = client.base_url if client.base_url else "In-Process TestClient"

    results_md = [
        "# Konecto Series 76 Assistant — Automated Evaluation Report",
        "",
        f"- **Model Configured:** `{chat_model}`",
        f"- **Embedding Model:** `{embed_model}`",
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
                payload = {"query": q}
                if session_id:
                    payload["session_id"] = session_id
                r = client.post("/api/conversation", json=payload)
                assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
                data = r.json()
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
        payload = {"query": q}
        if session_id:
            payload["session_id"] = session_id
        r = client.post("/api/conversation", json=payload)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        data = r.json()
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
