"""Validación contra el ORÁCULO (golden.json), independiente de lo que devolvieron las herramientas.

- oracle_verify(): todo número de la respuesta existe en la fila y el campo (familia/unidad) correctos del oráculo,
  usando el verificador estricto con filas del oráculo en lugar de las de la base.
- ui_matches_oracle(): cada actuador del ui_payload coincide campo a campo con el oráculo.
- states_value(): la respuesta contiene el valor que el oráculo da para (parte, campo).
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from app.verifier import PN_RE, VerificationResult, known_part_keys, pn_key, verify_answer

GOLDEN: List[Dict[str, Any]] = json.loads(
    (Path(__file__).parent / "oracle" / "golden.json").read_text(encoding="utf-8")
)["records"]
BY_PN: Dict[str, Dict[str, Any]] = {r["base_part_number"]: r for r in GOLDEN}
KNOWN = known_part_keys(GOLDEN)
TEXT_KEYS = ("diagnostics", "alerts", "chunks", "message")

FIELD_UNITS = {  # unidad con la que se escribe cada campo en una respuesta
    "Nm": ("on_off_torque_nm", "modulating_torque_nm"),
    "in-lbs": ("on_off_torque_in_lbs", "modulating_torque_in_lbs"),
}


def _walk_pns(obj: Any, out: Set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("base_part_number", "part_number", "na_part_number") and isinstance(v, str) and v in BY_PN:
                out.add(v)
            _walk_pns(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_pns(v, out)


def response_pns(resp: Dict[str, Any], extra_text: str = "") -> List[str]:
    found: Set[str] = set()
    for a in (resp.get("ui_payload") or {}).get("actuators") or []:
        if a.get("base_part_number") in BY_PN:
            found.add(a["base_part_number"])
    for tc in (resp.get("debug_trace") or {}).get("tool_calls") or []:
        _walk_pns(tc.get("raw_output"), found)
    for m in PN_RE.findall((resp.get("answer") or "") + " " + extra_text):
        for pn in BY_PN:
            if pn_key(pn) in (pn_key(m), pn_key(m) + "A"):
                found.add(pn)
    return sorted(found)


def text_facts(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Textos de alertas/diagnósticos/conocimiento de las herramientas y alertas localizadas de la UI (sin filas)."""
    facts: List[Dict[str, Any]] = []
    for tc in (resp.get("debug_trace") or {}).get("tool_calls") or []:
        raw = tc.get("raw_output")
        if isinstance(raw, dict):
            facts.append({k: raw[k] for k in TEXT_KEYS if k in raw})
    facts.append({"alerts": (resp.get("ui_payload") or {}).get("alerts") or []})
    rec = (resp.get("ui_payload") or {}).get("recommendation") or {}
    facts.append({"recommendation": {k: rec.get(k) for k in ("hard_constraints", "relaxed_constraints")}})
    return facts


def oracle_verify(resp: Dict[str, Any], query: str) -> VerificationResult:
    rows = [BY_PN[p] for p in response_pns(resp, query)]
    outs: List[Any] = [{"actuators": rows}] + text_facts(resp)
    return verify_answer(resp.get("answer") or "", outs, query, KNOWN)


def ui_matches_oracle(resp: Dict[str, Any]) -> List[str]:
    diffs: List[str] = []
    for a in (resp.get("ui_payload") or {}).get("actuators") or []:
        g = BY_PN.get(a.get("base_part_number"))
        if g is None:
            diffs.append(f"{a.get('base_part_number')}: no existe en el oráculo")
            continue
        for k, v in a.items():
            if k == "id" or k not in g:
                continue
            gv = g[k]
            same = (v is None and gv is None) or (
                v is not None and gv is not None and (float(v) == float(gv) if isinstance(v, (int, float)) and not isinstance(v, bool) and isinstance(gv, (int, float)) and not isinstance(gv, bool) else v == gv)
            )
            if not same:
                diffs.append(f"{a['base_part_number']}.{k}: ui={v!r} oráculo={gv!r}")
    return diffs


def _norm(text: str) -> str:
    t = re.sub(r"(?<=\d)[,   ](?=\d{3}\b)", "", text)  # 4,400 / 4 400 -> 4400
    return re.sub(r"(?<=\d),(?=\d)", ".", t)                       # 4,8 -> 4.8


def states_value(answer: str, value: float) -> bool:
    t = _norm(answer)
    reprs = {f"{value:g}", f"{value:.1f}", f"{value:.2f}", str(int(value)) if float(value).is_integer() else f"{value:g}"}
    return any(re.search(rf"(?<![\d.]){re.escape(r)}(?![\d]|\.\d)", t) for r in reprs)


def oracle_value(pn: str, field: str) -> Optional[float]:
    v = BY_PN[pn][field]
    return None if v is None else float(v)


# --------------------------------------------------------------------------------------------- catálogo y ranking (6C)
def _first(*vals: Any) -> Any:
    return next((v for v in vals if v is not None), None)


_METRIC = {   # misma semántica documentada de rank_actuators, calculada aquí desde el oráculo (independiente de la base)
    "torque": (lambda r: max([v for v in (r["on_off_torque_nm"], r["modulating_torque_nm"]) if v is not None], default=None), "max"),
    "power": (lambda r: r["motor_power_watts"], "max"),
    "speed": (lambda r: _first(r["speed_60hz_sec"], r["speed_dc_or_fixed_sec"]), "min"),
    "fla": (lambda r: _first(r["fla_60hz_amps"], r["fla_dc_or_fixed_amps"]), "min"),
    "lra": (lambda r: _first(r["lra_60hz_amps"], r["lra_dc_or_fixed_amps"]), "min"),
    "duty": (lambda r: max([v for v in (r["on_off_duty_cycle_pct"], r["modulating_duty_cycle_pct"]) if v is not None], default=None), "max"),
}


def golden_rank(args: Dict[str, Any]) -> Dict[str, Any]:
    fn, best = _METRIC[args["metric"]]
    order = args.get("order") or best
    rows = [r for r in GOLDEN if r["is_available"] and fn(r) is not None
            and all(r.get(k) == args[k] for k in ("voltage_num", "phase_type", "enclosure_type") if args.get(k) is not None)]
    if not rows:
        return {"value": None, "ties": 0, "pns": set()}
    v = (max if order == "max" else min)(fn(r) for r in rows)
    win = [r["base_part_number"] for r in rows if fn(r) == v]
    return {"value": v, "ties": len(win), "pns": set(win)}


def golden_counts(args: Dict[str, Any]) -> Dict[str, int]:
    rows = [r for r in GOLDEN if all(r.get(k) == args[k] for k in ("voltage_num", "phase_type", "enclosure_type") if args.get(k) is not None)]
    return {"models": len(rows), "available": sum(1 for r in rows if r["is_available"])}


def _nums(text: str) -> Set[float]:
    clean = re.sub(r"\d+\s?°", " ", PN_RE.sub(" ", text))     # «giro de 90°» es la definición de la métrica, no un dato
    return {float(x) for x in re.findall(r"\d+(?:\.\d+)?", clean)}


def catalog_oracle(resp: Dict[str, Any]) -> List[str]:
    """Verifica los turnos de catalog_overview / rank_actuators contra el oráculo: la salida de la herramienta coincide con lo que
    se calcula desde golden.json y toda cifra del texto (salvo el código de tamaño 76x) existe en ese cálculo."""
    fails: List[str] = []
    answer = resp.get("answer") or ""
    for tc in (resp.get("debug_trace") or {}).get("tool_calls") or []:
        name, args, out = tc.get("tool_name"), tc.get("arguments") or {}, tc.get("raw_output") or {}
        allowed: Set[float] = set()
        if name == "rank_actuators" and out.get("status") == "RANKED":
            g = golden_rank(args)
            if out["value"] != g["value"] or out["ties"] != g["ties"] or not set(out["part_numbers"]) <= g["pns"]:
                fails.append(f"oracle_rank: herramienta {out['value']}/{out['ties']} vs oráculo {g['value']}/{g['ties']}")
            allowed = {float(g["value"]), float(g["ties"]), float(len(out["part_numbers"]))} | ({float(args["voltage_num"])} if args.get("voltage_num") else set())
        elif name == "catalog_overview" and out.get("status") == "CATALOG_OVERVIEW":
            asp = out["aspect"]
            if asp == "summary":
                tot = len(GOLDEN); av = sum(1 for r in GOLDEN if r["is_available"])
                if (out["models"], out["available"]) != (tot, av):
                    fails.append(f"oracle_overview: summary {out['models']}/{out['available']} vs {tot}/{av}")
                allowed = {float(tot), float(av), float(tot - av), float(len({r['frame_size'] for r in GOLDEN})),
                           *{float(r["voltage_num"]) for r in GOLDEN}}
            elif asp == "count":
                g = golden_counts(args)
                if (out["models"], out["available"]) != (g["models"], g["available"]):
                    fails.append(f"oracle_overview: count {out['models']}/{out['available']} vs {g['models']}/{g['available']}")
                allowed = {float(g["models"]), float(g["available"])}
                # desglose por carcasa y sufijos de número de parte (de golden.json) que se muestran en «¿hay de 24 V?»
                allowed |= {float(r["voltage_num"]) for r in GOLDEN} | ({float(args["voltage_num"])} if args.get("voltage_num") else set())
                for enc in ("Weatherproof", "Explosionproof"):
                    allowed.add(float(golden_counts({**args, "enclosure_type": enc})["available"]))
                allowed |= {float(x) for r in GOLDEN for x in re.findall(r"\d+", r["base_part_number"].split("-")[1].split("/")[0])}
            elif asp in ("voltages", "phases", "enclosures"):
                col = {"voltages": "voltage_num", "phases": "phase_type", "enclosures": "enclosure_type"}[asp]
                exp: Dict[Any, int] = {}
                for r in GOLDEN:
                    if r["is_available"]:
                        exp[r[col]] = exp.get(r[col], 0) + 1
                got = {v["value"]: v["models"] for v in out["values"]}
                if got != exp:
                    fails.append(f"oracle_overview: {asp} {got} vs {exp}")
                allowed = {float(v) for v in exp.values()} | {float(k) for k in exp if isinstance(k, int)}
            elif asp in ("sizes", "compare_sizes"):
                for s in out["sizes"]:
                    fs = s["size"] - 760
                    rows = [r for r in GOLDEN if r["frame_size"] == fs and (asp == "compare_sizes" or r["is_available"])]
                    tq = [v for r in rows if r["is_available"] for v in (r["on_off_torque_nm"], r["modulating_torque_nm"]) if v is not None]
                    if s["torque_min_nm"] != min(tq) or s["torque_max_nm"] != max(tq):
                        fails.append(f"oracle_overview: tamaño {s['size']} torque {s['torque_min_nm']}-{s['torque_max_nm']} vs {min(tq)}-{max(tq)}")
                    if s["models"] != len(rows):
                        fails.append(f"oracle_overview: tamaño {s['size']} modelos {s['models']} vs {len(rows)}")
                    pw = [r["motor_power_watts"] for r in rows if r["motor_power_watts"] is not None]
                    allowed |= {float(s["size"]), float(len(rows)), float(min(tq)), float(max(tq))}
                    allowed |= {float(x) for x in (min(pw), max(pw))} if pw else set()
                    allowed |= {float(sum(1 for r in GOLDEN if r["frame_size"] == fs and r["is_available"]))}
                allowed |= {float(len(out["sizes"]))}
        else:
            continue
        stray = sorted(n for n in _nums(answer) if n not in allowed)
        if stray:
            fails.append(f"oracle_catalog_numbers: cifras no respaldadas por el oráculo: {stray}")
    return fails
