"""Banco de comprensión natural (evals/natural.json): lenguaje cotidiano, typos, dictado, seguimientos, superlativos...

Dos modos: HTTP contra un backend vivo (--base-url http://localhost:8001) o en proceso (FastAPI TestClient, sin --base-url).
Reporta por caso y por categoría: comprensión correcta (todas las comprobaciones del acto pasan), «respuesta no relacionada»
(se mostró algo que no se pidió: herramienta prohibida, tarjetas no pedidas o texto prohibido), caída en `uncertain` del router,
latencia p50/p95 y costo. Escribe NATURAL_REPORT.md y, con --results-json, el detalle para comparar corridas (--compare).

Uso: python evals/run_natural.py [--base-url URL] [--cat saludo ...] [--case NAT-001 ...] [--workers 3] [-v]
                                 [--results-json out.json] [--compare before.json] [--report ruta.md]
"""
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import argparse
import json
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_evals import EvalClient  # noqa: E402  (carga .env y la app)
from oracle_check import BY_PN, oracle_verify, ui_matches_oracle  # noqa: E402
from app.config import load_llm_config  # noqa: E402
from app.router import normalize_spoken_pn  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "natural.json"
REPORT_PATH = Path(__file__).resolve().parent / "NATURAL_REPORT.md"
MARKDOWN_RE = re.compile(r"\*\*|__|(?m:^\s*#{1,6}\s)|(?m:^\s*[-*•]\s)|\|.*\|")
COUNT_RE = re.compile(r"\b\d+\s+(?:modelos?|models?|tama[nñ]os?|sizes?|voltajes?|voltages?|opciones|options|variantes|variants|series)\b", re.I)

_NO_TOOLS = ["recommend_actuators", "lookup_actuator_by_part_number", "search_engineering_knowledge"]
_NOT_ASKED = [r"mejor opci[oó]n|best (option|match)|\d+\s?%\s*(de )?(ajuste|fit)|\bajuste\b", r"n[uú]mero de parte\s+.?76.?\b"]
_CONV = {"cards": False, "tools_forbidden": _NO_TOOLS, "must_not": _NOT_ASKED}
# Por defecto de cada acto (el caso puede sobreescribir cualquier clave). Aquí vive lo que el acto exige siempre.
ACT_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "greeting": {**_CONV, "followups_min": 3},
    "thanks": {**_CONV},
    "capabilities": {**_CONV, "followups_min": 2, "must_any": [r"ficha|spec|compar|recomend|recommend|concept"]},
    "about_project": {**_CONV, "must_any": [r"series 76|serie 76|actuador|actuator"]},
    "help_request": {**_CONV, "display": ["CLARIFICATION"], "options_between": [3, 5],
                     "must_not": _NOT_ASKED + [r"qu[eé] voltaje|what voltage|cu[aá]l es el voltaje|which voltage"]},
    "off_topic": {**_CONV},
}
# Fallos que significan «se contestó otra cosa / se mostró algo no pedido»
UNRELATED_TAGS = {"tool_forbidden", "cards_unexpected", "must_not"}


def merged_expect(case: Dict[str, Any]) -> Dict[str, Any]:
    ex = dict(ACT_DEFAULTS.get(case["act"], {}))
    ex.update(case.get("expect", {}))
    return ex


def check_numbers(resp: Dict[str, Any], query: str) -> List[str]:
    """Cifras de la respuesta contra el oráculo. Los conteos de catálogo («68 modelos») no son cifras de una ficha."""
    r2 = dict(resp)
    r2["answer"] = COUNT_RE.sub(" ", resp.get("answer") or "")
    res = oracle_verify(r2, normalize_spoken_pn(query)[0])
    return [] if res.ok else [f"numbers: cifras fuera del oráculo: {res.ungrounded}"]


def check_turn(resp: Dict[str, Any], query: str) -> List[str]:
    fails: List[str] = []
    answer = resp.get("answer") or ""
    if not answer.strip():
        fails.append("empty: respuesta vacía")
    fails += check_numbers(resp, query)
    diffs = ui_matches_oracle(resp)
    if diffs:
        fails.append(f"ui: ui_payload difiere del oráculo: {diffs[:3]}")
    if MARKDOWN_RE.search(answer):
        fails.append("markdown: la respuesta contiene Markdown")
    return fails


def check_expect(ex: Dict[str, Any], resp: Dict[str, Any]) -> List[str]:
    fails: List[str] = []
    ui = resp.get("ui_payload") or {}
    answer = resp.get("answer") or ""
    low = answer.lower()
    tools = [tc["tool_name"] for tc in (resp.get("debug_trace") or {}).get("tool_calls") or []]
    alerts = {a["code"] for a in ui.get("alerts") or []}
    parts = [a["base_part_number"] for a in ui.get("actuators") or []]

    for t in ex.get("tools_required", []):
        if t not in tools:
            fails.append(f"tool_missing: no llamó a {t} (llamó {tools})")
    for t in ex.get("tools_forbidden", []):
        if t in tools:
            fails.append(f"tool_forbidden: llamó a {t}")
    if "display" in ex and ui.get("display_type") not in ex["display"]:
        fails.append(f"display: display_type={ui.get('display_type')!r}, esperado {ex['display']}")
    for a in ex.get("alerts_required", []):
        if a not in alerts:
            fails.append(f"alert_missing: falta la alerta {a} (hay {sorted(alerts)})")
    for a in ex.get("alerts_forbidden", []):
        if a in alerts:
            fails.append(f"alert_forbidden: alerta prohibida {a}")
    if ex.get("cards") is True and not parts:
        fails.append("cards_missing: debía mostrar tarjetas y no hay")
    if ex.get("cards") is False and parts:
        fails.append(f"cards_unexpected: no debía haber tarjetas y hay {parts}")
    if "max_cards" in ex and len(parts) > ex["max_cards"]:
        fails.append(f"cards_unexpected: {len(parts)} tarjetas, máximo {ex['max_cards']}: {parts}")
    if "parts_any" in ex and not set(ex["parts_any"]) & set(parts):
        fails.append(f"parts: ninguna de {ex['parts_any'][:4]} en las tarjetas {parts[:5]}")
    if "parts_all" in ex and not set(ex["parts_all"]) <= set(parts):
        fails.append(f"parts: faltan {sorted(set(ex['parts_all']) - set(parts))} en {parts[:5]}")
    if "ui_all_enclosure" in ex:
        bad = [p for p in parts if BY_PN[p]["enclosure_type"] != ex["ui_all_enclosure"]]
        if not parts or bad:
            fails.append(f"enclosure: se esperaban solo {ex['ui_all_enclosure']} y hay {parts[:4]} (mal: {bad[:3]})")
    if "enclosure_if_cards" in ex and parts:
        bad = [p for p in parts if BY_PN[p]["enclosure_type"] != ex["enclosure_if_cards"]]
        if bad:
            fails.append(f"enclosure: se esperaban solo {ex['enclosure_if_cards']} y hay {bad[:3]}")
    if "options_between" in ex:
        n = len((ui.get("clarification") or {}).get("options") or [])
        lo, hi = ex["options_between"]
        if not lo <= n <= hi:
            fails.append(f"options: opciones de aclaración={n}, esperado {lo}-{hi}")
    if "followups_min" in ex and len(ui.get("suggested_followups") or []) < ex["followups_min"]:
        fails.append(f"followups: {len(ui.get('suggested_followups') or [])} botones, esperado ≥{ex['followups_min']}")
    for p in ex.get("must", []):
        if not re.search(p, low):
            fails.append(f"must: falta /{p}/: {answer[:120]!r}")
    if ex.get("must_any") and not any(re.search(p, low) for p in ex["must_any"]):
        fails.append(f"must: ninguna de {ex['must_any']}: {answer[:120]!r}")
    for p in ex.get("must_not", []):
        if re.search(p, low):
            fails.append(f"must_not: contiene lo prohibido /{p}/: {answer[:120]!r}")
    return fails


def run_case(client: EvalClient, case: Dict[str, Any], verbose: bool) -> Dict[str, Any]:
    session_id: Optional[str] = None
    prev: Optional[Dict[str, Any]] = None
    stats = {"latency_ms": 0.0, "last_ms": 0.0, "tokens": 0, "cost": 0.0}
    fails: List[str] = []
    last: Dict[str, Any] = {}
    for turn in case["turns"]:
        if isinstance(turn, dict) and "pick_option" in turn:
            opts = ((prev or {}).get("ui_payload") or {}).get("clarification", {}).get("options") or []
            if len(opts) <= turn["pick_option"]:
                fails.append("options: el turno anterior no ofreció la opción pedida")
                break
            query = opts[turn["pick_option"]]["value"]
        else:
            query = turn
        payload: Dict[str, Any] = {"query": query}
        if case.get("lang") in ("es", "en"):      # "mixed": sin locale, el backend lo detecta
            payload["locale"] = case["lang"]
        if session_id:
            payload["session_id"] = session_id
        t0 = time.perf_counter()
        try:
            r = client.post("/api/conversation", json=payload)
        except Exception as exc:  # noqa: BLE001
            fails.append(f"http: excepción {type(exc).__name__}: {exc}")
            break
        wall = (time.perf_counter() - t0) * 1000
        if r.status_code != 200:
            fails.append(f"http: HTTP {r.status_code}: {r.text[:160]}")
            break
        resp = r.json()
        session_id = resp["session_id"]
        dbg = resp.get("debug_trace") or {}
        stats["latency_ms"] += wall
        stats["last_ms"] = wall
        stats["tokens"] += (dbg.get("token_usage") or {}).get("total_tokens", 0)
        stats["cost"] += dbg.get("cost_usd_estimate", 0.0)
        fails += [f"[turno {query[:30]!r}] {f}" for f in check_turn(resp, query)]
        prev = last = resp
        if verbose:
            print(f"      > {query}\n      < ({resp.get('intent')}/{(resp.get('ui_payload') or {}).get('display_type')}) {resp.get('answer')}")
    if last:
        fails += check_expect(merged_expect(case), last)
    steps = (last.get("debug_trace") or {}).get("steps") or []
    router_rule = next((s.get("detail") for s in steps if s["name"] == "router"), None)
    classifier = next((s.get("detail") for s in steps if s["name"] == "classifier"), None)
    tags = {re.match(r"(?:\[[^\]]*\]\s*)?(\w+):", f).group(1) if re.match(r"(?:\[[^\]]*\]\s*)?(\w+):", f) else "other" for f in fails}
    return {"id": case["id"], "category": case["category"], "act": case["act"], "lang": case["lang"], "real": bool(case.get("real")),
            "turns": [t if isinstance(t, str) else str(t) for t in case["turns"]], "fails": fails, "stats": stats,
            "unrelated": bool(tags & UNRELATED_TAGS), "router_rule": router_rule, "classifier": classifier,
            "uncertain": router_rule == "uncertain", "intent": last.get("intent"),
            "display": (last.get("ui_payload") or {}).get("display_type"), "answer": last.get("answer", "")}


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "n/a"


def percentile(xs: List[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(results)
    ok = sum(1 for r in results if not r["fails"])
    lat = [r["stats"]["last_ms"] for r in results]
    cats: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        cats.setdefault(r["category"], []).append(r)
    return {"n": n, "ok": ok, "unrelated": sum(r["unrelated"] for r in results), "uncertain": sum(r["uncertain"] for r in results),
            "p50": statistics.median(lat) if lat else 0, "p95": percentile(lat, 0.95), "cost": sum(r["stats"]["cost"] for r in results),
            "cats": {c: (sum(1 for r in rs if not r["fails"]), len(rs)) for c, rs in cats.items()}}


def main() -> int:
    ap = argparse.ArgumentParser(description="Banco de comprensión natural")
    ap.add_argument("--base-url", default=None, help="backend HTTP vivo; sin él, en proceso (TestClient)")
    ap.add_argument("--case", "-c", action="append")
    ap.add_argument("--cat", action="append", help="categoría(s)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--report", default=None)
    ap.add_argument("--results-json", default=None)
    ap.add_argument("--compare", default=None, help="results-json de una corrida anterior (antes/después por categoría)")
    ap.add_argument("--label", default="")
    args = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    if args.case:
        cases = [c for c in cases if c["id"] in set(args.case)]
    if args.cat:
        cases = [c for c in cases if c["category"] in set(args.cat)]
    cfg = load_llm_config()
    client = EvalClient(base_url=args.base_url)
    mode = f"HTTP {args.base_url}" if args.base_url else "en proceso"
    print(f"\nBanco natural: {len(cases)} casos | {mode} | proveedor={cfg.provider} modelo={cfg.chat_model}\n")

    workers = max(1, args.workers) if args.base_url else 1   # TestClient en proceso: secuencial
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda c: run_case(client, c, args.verbose), cases))
    for r in results:
        print(f"[{'PASS' if not r['fails'] else 'FAIL'}] {r['id']} {r['category']:<18} {r['act']:<22} {r['stats']['last_ms']:>6.0f} ms  rule={r['router_rule']} "
              f"{'UNRELATED' if r['unrelated'] else ''}  {r['turns'][-1][:50]!r}")
        for f in r["fails"]:
            print(f"       - {f}")

    s = summarize(results)
    print(f"\nComprensión correcta {s['ok']}/{s['n']} ({pct(s['ok'], s['n'])}) | no relacionada {s['unrelated']} ({pct(s['unrelated'], s['n'])}) | "
          f"uncertain {s['uncertain']} ({pct(s['uncertain'], s['n'])}) | p50 {s['p50']:.0f} ms p95 {s['p95']:.0f} ms | costo USD {s['cost']:.5f}")

    before = None
    if args.compare:
        before = summarize(json.loads(Path(args.compare).read_text(encoding="utf-8")))
    md = ["# Banco de comprensión natural", "",
          f"- Fecha: `{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC`" + (f" · {args.label}" if args.label else ""),
          f"- Modo: {mode} · proveedor/modelo: `{cfg.provider}` / `{cfg.chat_model}`",
          f"- Casos: {s['n']} (reales de chat_messages: {sum(r['real'] for r in results)})", "",
          "## Resumen", "", "| Métrica | Valor |", "|---|---|",
          f"| Comprensión correcta | **{s['ok']}/{s['n']} ({pct(s['ok'], s['n'])})** |",
          f"| Respuesta no relacionada (tool/tarjetas/texto no pedidos) | {s['unrelated']} ({pct(s['unrelated'], s['n'])}) |",
          f"| Caída en `uncertain` del router | {s['uncertain']} ({pct(s['uncertain'], s['n'])}) |",
          f"| Latencia último turno p50 / p95 | {s['p50']:.0f} ms / {s['p95']:.0f} ms |",
          f"| Costo total (estimado) | USD {s['cost']:.5f} (por caso {s['cost'] / max(1, s['n']):.6f}) |", "",
          "## Por categoría", ""]
    if before:
        md += ["| Categoría | Antes | Ahora |", "|---|---|---|"]
        for c in s["cats"]:
            b = before["cats"].get(c)
            md.append(f"| {c} | {f'{b[0]}/{b[1]}' if b else '-'} | {s['cats'][c][0]}/{s['cats'][c][1]} |")
        md.append(f"| **Global** | {before['ok']}/{before['n']} ({pct(before['ok'], before['n'])}) | {s['ok']}/{s['n']} ({pct(s['ok'], s['n'])}) |")
    else:
        md += ["| Categoría | Aciertos | Tasa |", "|---|---|---|"]
        md += [f"| {c} | {a}/{t} | {pct(a, t)} |" for c, (a, t) in s["cats"].items()]
    md += ["", "## Por caso", "", "| Caso | Categoría | Acto | Estado | Regla router | Último mensaje |", "|---|---|---|---|---|---|"]
    for r in results:
        md.append(f"| {r['id']}{' (real)' if r['real'] else ''} | {r['category']} | {r['act']} | {'PASS' if not r['fails'] else 'FAIL' + (' (no relacionada)' if r['unrelated'] else '')} | "
                  f"{r['router_rule']} | {r['turns'][-1][:60].replace('|', '/')} |")
    bad = [r for r in results if r["fails"]]
    if bad:
        md += ["", "## Fallos (más graves primero: respuesta no relacionada)", ""]
        for r in sorted(bad, key=lambda r: (not r["unrelated"], r["id"])):
            md.append(f"- **{r['id']}** [{r['category']}] `{r['turns'][-1][:70]}` → ({r['intent']}/{r['display']}) {r['answer'][:150]!r}")
            md += [f"  - {f}" for f in r["fails"][:4]]
    (Path(args.report) if args.report else REPORT_PATH).write_text("\n".join(md) + "\n", encoding="utf-8")
    if args.results_json:
        Path(args.results_json).write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"Reporte: {args.report or REPORT_PATH}")
    return 0 if s["ok"] == s["n"] else 1


if __name__ == "__main__":
    sys.exit(main())
