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
