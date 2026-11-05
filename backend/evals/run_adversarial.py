"""Corrida CON LLM de los casos adversarios (evals/adversarial.json) contra el oráculo.

Por turno se valida SIEMPRE: (1) todo número+unidad de la respuesta existe en la fila y campo correctos del oráculo,
(2) las filas del ui_payload coinciden con el oráculo, (3) respuesta sin Markdown y corta, (4) verificación != unverified.
Por caso se valida `expect` (intent, display_type, herramientas, estados, alertas, frases esperadas/prohibidas...).
Imprime costo, latencia, tokens y reintentos (verificador / transporte) por caso y escribe ADVERSARIAL_REPORT.md.

Uso:  python evals/run_adversarial.py [--case ADV-03 ...] [--base-url http://localhost:8001] [-v]
"""
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_evals import EvalClient  # noqa: E402  (carga .env y la app)
from oracle_check import BY_PN, oracle_value, oracle_verify, states_value, ui_matches_oracle  # noqa: E402
from app.config import load_llm_config  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "adversarial.json"
REPORT_PATH = Path(__file__).resolve().parent / "ADVERSARIAL_REPORT.md"
MARKDOWN_RE = re.compile(r"\*\*|__|(?m:^\s*#{1,6}\s)|(?m:^\s*[-*•]\s)|\|.*\|")
MAX_WORDS_DEFAULT = 60


def _tool_statuses(resp: Dict[str, Any]) -> List[str]:
    out = []
    for tc in (resp.get("debug_trace") or {}).get("tool_calls") or []:
        raw = tc.get("raw_output")
        if isinstance(raw, dict) and raw.get("status"):
            out.append(raw["status"])
    return out


def check_turn(resp: Dict[str, Any], query: str) -> List[str]:
    """Comprobaciones globales de un turno; devuelve los fallos."""
    fails: List[str] = []
    answer = resp.get("answer") or ""
    ui = resp.get("ui_payload") or {}
    if (resp.get("verification") or {}).get("status") == "unverified":
        fails.append("verification.status=unverified")
    res = oracle_verify(resp, query)
    if not res.ok:
        fails.append(f"números fuera del oráculo (unidad/fila): {res.ungrounded}")
    diffs = ui_matches_oracle(resp)
    if diffs:
        fails.append(f"ui_payload difiere del oráculo: {diffs[:3]}")
    if MARKDOWN_RE.search(answer):
        fails.append("la respuesta contiene Markdown")
    if resp.get("intent") != "clarify" and len(answer.split()) > MAX_WORDS_DEFAULT:
        fails.append(f"respuesta larga ({len(answer.split())} palabras)")
    if not answer.strip():
        fails.append("respuesta vacía")
    return fails


def check_expect(case: Dict[str, Any], resp: Dict[str, Any]) -> List[str]:
    ex = case.get("expect", {})
    fails: List[str] = []
    ui = resp.get("ui_payload") or {}
    answer = resp.get("answer") or ""
    low = answer.lower()
    tools = [tc["tool_name"] for tc in (resp.get("debug_trace") or {}).get("tool_calls") or []]
    alerts = {a["code"] for a in ui.get("alerts") or []}
    parts = [a["base_part_number"] for a in ui.get("actuators") or []]

    if "intent" in ex and resp.get("intent") not in ex["intent"]:
        fails.append(f"intent={resp.get('intent')!r}, esperado {ex['intent']}")
    if "display_type" in ex and ui.get("display_type") not in ex["display_type"]:
        fails.append(f"display_type={ui.get('display_type')!r}, esperado {ex['display_type']}")
    for t in ex.get("tools_include", []):
        if t not in tools:
            fails.append(f"no llamó a {t} (llamó {tools})")
    if "tool_status_any" in ex and not set(ex["tool_status_any"]) & set(_tool_statuses(resp)):
        fails.append(f"estado de herramienta {_tool_statuses(resp)}, esperado alguno de {ex['tool_status_any']}")
    if "alerts_any" in ex and not set(ex["alerts_any"]) & alerts:
        fails.append(f"alertas {sorted(alerts)}, esperada alguna de {ex['alerts_any']}")
    for pn in ex.get("ui_parts_include", []):
        if pn not in parts:
            fails.append(f"{pn} no está en ui_payload.actuators {parts}")
    if ex.get("no_ui_actuators") and parts:
        fails.append(f"no debía haber tarjetas y hay {parts}")
    if "ui_all_enclosure" in ex:
        bad = [p for p in parts if BY_PN[p]["enclosure_type"] != ex["ui_all_enclosure"]]
        if not parts or bad:
            fails.append(f"se esperaban solo {ex['ui_all_enclosure']} y hay {parts} (mal: {bad})")
    if "options_between" in ex:
        n = len((ui.get("clarification") or {}).get("options") or [])
        lo, hi = ex["options_between"]
        if not lo <= n <= hi:
            fails.append(f"opciones de aclaración={n}, esperado {lo}-{hi}")
    if "answer_any" in ex and not any(re.search(p, low) for p in ex["answer_any"]):
        fails.append(f"la respuesta no contiene ninguno de {ex['answer_any']}: {answer[:140]!r}")
    for p in ex.get("answer_none", []):
        if re.search(p, low):
            fails.append(f"la respuesta contiene lo prohibido /{p}/: {answer[:140]!r}")
    for forbidden, unless in ex.get("answer_none_unless", []):
        # En 24V la ficha trae una sola corriente (*_dc_or_fixed_*): citarla junto a "60 Hz" solo es falso si el texto
        # NO aclara que no hay valores separados 50/60 Hz.
        if re.search(forbidden, low) and not re.search(unless, low):
            fails.append(f"la respuesta contiene lo prohibido /{forbidden}/ sin aclarar que no hay valores 50/60 Hz: {answer[:140]!r}")
    for ms in ex.get("must_state", []):
        v = oracle_value(ms["pn"], ms["field"])
        if v is not None and not states_value(answer, v):
            fails.append(f"debía decir {ms['pn']}.{ms['field']}={v:g} y no aparece: {answer[:140]!r}")
    if "max_words" in ex and len(answer.split()) > ex["max_words"]:
        fails.append(f"más de {ex['max_words']} palabras")
    return fails


TRACE_DIR: Optional[Path] = None


def run_case(client: EvalClient, case: Dict[str, Any], verbose: bool) -> Dict[str, Any]:
    session_id: Optional[str] = None
    prev: Optional[Dict[str, Any]] = None
    stats = {"latency_ms": 0.0, "tokens": 0, "cost": 0.0, "verifier_retries": 0, "llm_retries": 0}
    fails: List[str] = []
    last: Dict[str, Any] = {}
    for turn in case["turns"]:
        if isinstance(turn, dict) and "pick_option" in turn:
            opts = ((prev or {}).get("ui_payload") or {}).get("clarification", {}).get("options") or []
            if len(opts) <= turn["pick_option"]:
                fails.append("el turno anterior no ofreció la opción pedida")
                break
            query = opts[turn["pick_option"]]["value"]
        else:
            query = turn
        payload: Dict[str, Any] = {"query": query}
        if case.get("lang") in ("es", "en"):      # "mixed" (spanglish): sin locale, el backend lo detecta
            payload["locale"] = case["lang"]
        if session_id:
            payload["session_id"] = session_id
        t0 = time.perf_counter()
        try:
            r = client.post("/api/conversation", json=payload)
        except Exception as exc:  # noqa: BLE001
            fails.append(f"excepción en la petición: {type(exc).__name__}: {exc}")
            break
        wall = (time.perf_counter() - t0) * 1000
        if r.status_code != 200:
            fails.append(f"HTTP {r.status_code}: {r.text[:160]}")
            break
        resp = r.json()
        session_id = resp["session_id"]
        dbg = resp.get("debug_trace") or {}
        tu = dbg.get("token_usage") or {}
        stats["latency_ms"] += wall
        stats["tokens"] += tu.get("total_tokens", 0)
        stats["cost"] += dbg.get("cost_usd_estimate", 0.0)
        stats["verifier_retries"] += tu.get("retries", 0)
        stats["llm_retries"] += tu.get("llm_retries", 0)
        if TRACE_DIR:
            TRACE_DIR.mkdir(parents=True, exist_ok=True)
            (TRACE_DIR / f"{case['id']}.json").write_text(
                json.dumps({"query": query, "wall_ms": round(wall), "response": resp}, ensure_ascii=False, indent=2), encoding="utf-8")
        fails += [f"[turno '{query[:40]}'] {f}" for f in check_turn(resp, query)]
        prev = last = resp
        if verbose:
            print(f"      > {query}\n      < ({resp.get('intent')}) {resp.get('answer')}")
    if last:
        fails += check_expect(case, last)
    return {"id": case["id"], "category": case["category"], "lang": case["lang"], "fails": fails, "stats": stats,
            "intent": last.get("intent"), "verification": (last.get("verification") or {}).get("status"),
            "answer": last.get("answer", "")}


def main() -> int:
    ap = argparse.ArgumentParser(description="Casos adversarios con LLM validados contra el oráculo")
    ap.add_argument("--case", "-c", action="append", help="ID(s) de caso, p. ej. ADV-03")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--trace-dir", default=None, help="guarda la respuesta completa de cada caso (JSON)")
    ap.add_argument("--pause", type=float, default=0.0, help="segundos entre casos (límites de tasa)")
    ap.add_argument("--cases", default=None, help="JSON de casos alterno (p. ej. evals/heldout.json)")
    ap.add_argument("--report", default=None, help="ruta del informe Markdown alterno")
    ap.add_argument("--results-json", default=None, help="vuelca los resultados por caso (JSON) para comparar corridas")
    args = ap.parse_args()

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    global TRACE_DIR
    TRACE_DIR = Path(args.trace_dir) if args.trace_dir else None
    cases = json.loads(Path(args.cases or CASES_PATH).read_text(encoding="utf-8"))["cases"]
    if args.case:
        cases = [c for c in cases if c["id"] in set(args.case)]
    cfg = load_llm_config()
    client = EvalClient(base_url=args.base_url)
    print(f"\nCasos adversarios: {len(cases)} | proveedor={cfg.provider} modelo={cfg.chat_model}\n")

    results = []
    for case in cases:
        res = run_case(client, case, args.verbose)
        results.append(res)
        s = res["stats"]
        mark = "PASS" if not res["fails"] else "FAIL"
        print(f"[{mark}] {res['id']} {res['lang']} {res['category']:<18} {s['latency_ms']:>7.0f} ms  {s['tokens']:>5} tok  "
              f"USD {s['cost']:.5f}  reint(verif/llm)={s['verifier_retries']}/{s['llm_retries']}  "
              f"intent={res['intent']} ver={res['verification']}")
        for f in res["fails"]:
            print(f"       - {f}")
        if args.pause:
            time.sleep(args.pause)

    passed = sum(1 for r in results if not r["fails"])
    tot = {k: sum(r["stats"][k] for r in results) for k in ("latency_ms", "tokens", "cost", "verifier_retries", "llm_retries")}
    print(f"\n{passed}/{len(results)} casos pasan | latencia total {tot['latency_ms']/1000:.1f} s | tokens {tot['tokens']} | "
          f"costo USD {tot['cost']:.5f} | reintentos verificador={tot['verifier_retries']} transporte={tot['llm_retries']}")

    md = ["# Casos adversarios — corrida con LLM contra el oráculo", "",
          f"- Proveedor/modelo: `{cfg.provider}` / `{cfg.chat_model}`",
          f"- Fecha: `{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC`",
          f"- Resultado: **{passed}/{len(results)}**", "",
          "| Caso | Idioma | Categoría | Estado | Latencia ms | Tokens | Costo USD | Reint. verif/LLM | Intent | Verificación |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        s = r["stats"]
        md.append(f"| {r['id']} | {r['lang']} | {r['category']} | {'PASS' if not r['fails'] else 'FAIL'} | {s['latency_ms']:.0f} | "
                  f"{s['tokens']} | {s['cost']:.5f} | {s['verifier_retries']}/{s['llm_retries']} | {r['intent']} | {r['verification']} |")
    bad = [r for r in results if r["fails"]]
    if bad:
        md += ["", "## Fallos", ""]
        for r in bad:
            md.append(f"- **{r['id']}**: " + " | ".join(r["fails"]))
    report_path = Path(args.report) if args.report else REPORT_PATH
    report_path.write_text(chr(10).join(md) + chr(10), encoding="utf-8")
    if args.results_json:
        Path(args.results_json).write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"Reporte: {report_path}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
