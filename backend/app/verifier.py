"""Verificador numerico estricto (REGLA 4: ningun numero que vea el usuario puede venir del LLM).

verify_answer() comprueba cada cifra de la respuesta final:
  1. Cifra CON unidad (Nm, in-lbs, s, A, W, %, ciclos/h, arranques/h, V, Hz): el par valor+unidad debe existir en la
     FAMILIA de campos correcta (Nm <- *_nm, s <- speed_*, A <- fla_*/lra_*, W <- motor_power_watts, %, ...).
       - Si la frase cita numeros de parte, el valor debe pertenecer a UNA DE ESAS filas (con una sola fila citada es
         estricto por fila; si cita varias y no se puede atribuir, basta con que exista en alguna de las citadas).
       - Si la frase no cita numero de parte, basta con que exista en esa familia en alguna fila del turno.
       - Tambien valen los pares valor+unidad presentes en textos de las herramientas (alertas, diagnosticos,
         conocimiento) y en el mensaje del usuario (que lo escribio el usuario).
     Una conversion legitima (p. ej. Nm <-> in-lbs) solo pasa si AMBOS valores estan ya en la salida de la herramienta.
  2. Cifra SIN unidad (cantidades, tamanos, enumeraciones): debe existir en algun lugar de las salidas del turno o del
     mensaje del usuario (regla anterior), salvo las excepciones de config/verifier.json (marcadores de lista, "90 grados").
  3. Numeros de parte: deben existir en la base de datos o ser eco textual del usuario.
Es una funcion pura (sin red ni DB): los numeros de parte conocidos llegan por parametro.
"""
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "verifier.json"

# Numero de parte completo (con guion) o codigo de tamano (761A, 766A00)
PN_RE = re.compile(r"\b76\d[A-Za-z0-9]{0,4}-[A-Za-z0-9]{4,9}(?:/[A-Za-z])?|\b76\d[A-Za-z]\d{0,2}\b", re.IGNORECASE)
# Token numerico: sin letras/digitos pegados por la izquierda (descarta T4, S4, IIB...)
NUM_RE = re.compile(r"(?<![A-Za-z0-9_])\d+(?:[.,   ]\d+)*")
LIST_MARKER_RE = re.compile(r"(?m)^\s*\d{1,2}[.)]\s")
PRECISION = 6

# Unidad inmediatamente despues del numero. Las de una letra distinguen mayusculas (A, W, V, s; "a" es "to" en español).
_UNIT_PATTERNS: List[Tuple[str, str]] = [
    ("cycles/h", r"(?i:cycles?\s*(?:/|per)\s*(?:h|hr|hour)|ciclos?\s*(?:/|por)\s*(?:h|hora))"),
    ("starts/h", r"(?i:starts?\s*(?:/|per)\s*(?:h|hr|hour)|arranques?\s*(?:/|por)\s*(?:h|hora))"),
    ("in-lbs", r"(?i:in\.?\s*[-·.]?\s*lbs?\.?|inch[- ]pounds?|libras?[- ]pulgadas?)"),
    ("Nm", r"(?i:n\s*[·.\-]?\s*m(?![a-z])|newton[- ]?(?:metros?|meters?))"),
    ("Hz", r"(?i:hz|hertz)"),
    ("%", r"%|(?i:percent|por\s*ciento)"),
    ("s", r"(?:s|(?i:sec|secs|seconds?|segundos?|seg))(?![A-Za-z])"),
    ("A", r"(?:A|(?i:amps?|amperes?|amperios?))(?![A-Za-z])"),
    ("W", r"(?:W|(?i:watts?|vatios?))(?![A-Za-z])"),
    ("V", r"(?:V|(?i:volts?|voltios?))(?![A-Za-z])"),
]
_UNIT_RES = [(u, re.compile(r"\s{0,2}(?:" + p + r")")) for u, p in _UNIT_PATTERNS]
_CONNECTOR_RE = re.compile(r"\s*(?:/|,|-|–|—|to|and|or|y|o|a|e)?\s*", re.IGNORECASE)


@dataclass
class VerificationResult:
    numbers_checked: int = 0
    ungrounded: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.ungrounded

    @property
    def status(self) -> str:
        return "verified" if self.ok else "unverified"


@lru_cache(maxsize=1)
def _config() -> Dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def pn_key(pn: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", pn.upper())


def known_part_keys(rows: Iterable[Dict[str, Any]]) -> Set[str]:
    """Claves normalizadas de numeros de parte validos: completo (con y sin /A), prefijo de tamano y size_code."""
    keys: Set[str] = set()
    for r in rows:
        bpn = r["base_part_number"]
        keys.add(pn_key(bpn))
        keys.add(pn_key(bpn.split("/")[0]))
        keys.add(pn_key(bpn.split("-")[0]))
        if r.get("size_code"):
            keys.add(pn_key(r["size_code"]))
    return keys


def load_known_parts() -> Set[str]:
    from app.database import get_db_cursor

    with get_db_cursor() as cur:
        cur.execute("SELECT base_part_number, size_code FROM actuators;")
        return known_part_keys(cur.fetchall())


def _strip_pns(text: str) -> Tuple[str, List[str]]:
    found = [m.group(0) for m in PN_RE.finditer(text)]
    return PN_RE.sub(" ", text), found


def _candidates(token: str) -> List[float]:
    tok = token.replace(" ", "").replace(" ", "").replace(" ", "")
    parts = re.split(r"[.,]", tok)
    if len(parts) == 1:
        return [float(tok)]
    cands: List[float] = []
    if len(parts) == 2:
        cands.append(float(parts[0] + "." + parts[1]))
    if all(len(p) == 3 for p in parts[1:]) and 1 <= len(parts[0]) <= 3:
        cands.append(float("".join(parts)))
    return cands or [float(p) for p in parts]


def _apply_exceptions(body: str) -> str:
    cfg = _config()
    if cfg.get("skip_list_markers"):
        body = LIST_MARKER_RE.sub(" ", body)
    for pat in cfg.get("free_patterns", []):
        body = re.sub(pat, " ", body, flags=re.IGNORECASE)
    return body


def extract_numbers(text: str, apply_exceptions: bool = False) -> List[Tuple[str, List[float]]]:
    """[(texto_del_token, [valores candidatos])] ignorando numeros de parte (se validan aparte)."""
    body, _ = _strip_pns(text)
    if apply_exceptions:
        body = _apply_exceptions(body)
    return [(m.group(0), _candidates(m.group(0))) for m in NUM_RE.finditer(body)]


@dataclass
class Quantity:
    raw: str
    cands: List[float]
    unit: Optional[str]


def extract_quantities(body: str) -> List[Quantity]:
    """Numeros con su unidad (None si no la llevan). Una lista "26/32 s" o "26 y 32 s" comparte la unidad final."""
    matches = list(NUM_RE.finditer(body))
    units: List[Optional[str]] = [None] * len(matches)
    for i, m in enumerate(matches):
        tail = body[m.end(): m.end() + 28]
        for unit, rx in _UNIT_RES:
            um = rx.match(tail)
            if um:
                units[i] = unit
                break
    for i in range(len(matches) - 2, -1, -1):  # herencia hacia la izquierda por conectores
        if units[i] is None and units[i + 1] is not None:
            gap = body[matches[i].end(): matches[i + 1].start()]
            if len(gap) <= 6 and _CONNECTOR_RE.fullmatch(gap):
                units[i] = units[i + 1]
    return [Quantity(m.group(0), _candidates(m.group(0)), units[i]) for i, m in enumerate(matches)]


# ------------------------------------------------------------------------------------------- hechos de las herramientas
def family_of_key(key: str) -> str:
    k = key.lower()
    if k.endswith("_in_lbs"):
        return "in-lbs"
    if k.endswith("_nm"):
        return "Nm"
    if k.startswith("speed_") or k.endswith("_sec"):
        return "s"
    if k.startswith(("fla_", "lra_")) or k.endswith("_amps"):
        return "A"
    if k.endswith("_watts"):
        return "W"
    if k.endswith("_pct"):
        return "%"
    if k == "cycles_per_hour":
        return "cycles/h"
    if k == "starts_per_hour":
        return "starts/h"
    if k == "voltage_num":
        return "V"
    if k.endswith("hz"):
        return "Hz"
    return ""


def _r(x: float) -> float:
    return round(float(x), PRECISION)


@dataclass
class Facts:
    rows: Dict[str, Dict[str, Set[float]]] = field(default_factory=dict)   # pn_key -> familia -> valores
    sizes: Dict[str, Set[str]] = field(default_factory=dict)                # size_code key -> pn_keys
    text: Dict[str, Set[float]] = field(default_factory=dict)               # familia -> valores (textos, usuario)
    loose: Set[float] = field(default_factory=set)                          # cualquier numero visto

    def add_text(self, fam: str, v: float) -> None:
        self.text.setdefault(fam, set()).add(_r(v))
        self.loose.add(_r(v))

    def row(self, key: str) -> Dict[str, Set[float]]:
        return self.rows.setdefault(key, {})


def _add_strings_pairs(s: str, sink) -> None:
    body, _ = _strip_pns(s)
    for q in extract_quantities(body):
        for c in q.cands:
            sink(q.unit or "", c)


def _walk(obj: Any, facts: Facts, current_row: Optional[Dict[str, Set[float]]], key: str = "") -> None:
    if obj is None or isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        v = _r(obj)
        facts.loose.add(v)
        fam = family_of_key(key)
        if current_row is not None:
            current_row.setdefault(fam, set()).add(v)
        elif fam:
            facts.add_text(fam, v)
    elif isinstance(obj, str):
        if current_row is not None:  # texto de una fila (p. ej. power_supply "110V ..."): respalda solo a esa fila
            _add_strings_pairs(obj, lambda fam, c: (current_row.setdefault(fam, set()).add(_r(c)), facts.loose.add(_r(c))))
        else:
            _add_strings_pairs(obj, lambda fam, c: facts.add_text(fam, c) if fam else facts.loose.add(_r(c)))
    elif isinstance(obj, dict):
        pn = obj.get("base_part_number") or obj.get("part_number")
        row = current_row
        if isinstance(pn, str) and PN_RE.search(pn):
            k = pn_key(pn)
            row = facts.row(k)
            if obj.get("size_code"):
                facts.sizes.setdefault(pn_key(obj["size_code"]), set()).add(k)
            facts.sizes.setdefault(pn_key(pn.split("-")[0])[:4], set()).add(k)
        for k2, v in obj.items():
            # los nombres de campo llevan la frecuencia (fla_60hz_amps): "60 Hz" queda respaldado por el campo
            for n in re.findall(r"(\d+)hz", str(k2).lower()):
                facts.add_text("Hz", float(n))
            _walk(v, facts, row, str(k2))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk(v, facts, current_row, key)


def build_facts(tool_outputs: Iterable[Any], user_message: str) -> Facts:
    facts = Facts()
    for out in tool_outputs:
        _walk(out, facts, None)
    # mensaje del usuario: lo que escribio el con su unidad; sin unidad vale para cualquier familia
    body, _ = _strip_pns(user_message)
    for q in extract_quantities(body):
        for c in q.cands:
            if q.unit:
                facts.add_text(q.unit, c)
            else:
                facts.loose.add(_r(c))
                facts.text.setdefault("*", set()).add(_r(c))
    return facts


def allowed_numbers(tool_outputs: Iterable[Any], user_message: str) -> Set[float]:
    """Compat: conjunto plano de numeros presentes en salidas y mensaje (regla antigua, sin unidades)."""
    return build_facts(tool_outputs, user_message).loose


# ------------------------------------------------------------------------------------------- verificacion
_SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÑ¿¡0-9(])|\n+")


def _cited_rows(pns: List[str], facts: Facts) -> List[Dict[str, Set[float]]]:
    cited: List[Dict[str, Set[float]]] = []
    for pn in pns:
        k = pn_key(pn)
        exact = next((c for c in (k, k + "A") if c in facts.rows), None)  # con o sin "/A"
        if exact:
            cited.append(facts.rows[exact])
            continue
        # codigo de tamano (761A / 763B00): todas las filas de ese tamano
        for rk in facts.sizes.get(k[:4], ()):
            if rk.startswith(k) or len(k) <= 4:
                cited.append(facts.rows[rk])
    return cited


def _unit_ok(unit: str, cands: List[float], cited: List[Dict[str, Set[float]]], facts: Facts) -> bool:
    values = {_r(c) for c in cands}
    if values & facts.text.get(unit, set()) or values & facts.text.get("*", set()):
        return True
    pool = cited if cited else list(facts.rows.values())
    return any(values & row.get(unit, set()) for row in pool)


def verify_answer(
    answer: str,
    tool_outputs: Iterable[Any],
    user_message: str,
    known_parts: Set[str],
) -> VerificationResult:
    outs = list(tool_outputs)
    facts = build_facts(outs, user_message)
    user_pns = {pn_key(p) for p in PN_RE.findall(user_message)}
    res = VerificationResult()

    _, answer_pns = _strip_pns(answer)
    for pn in dict.fromkeys(answer_pns):
        res.numbers_checked += 1
        k = pn_key(pn)
        if k not in known_parts and k not in user_pns:
            res.ungrounded.append(f"PN:{pn.upper()}")

    flagged: Set[str] = set(res.ungrounded)
    for sentence in _SENT_SPLIT.split(_apply_exceptions(answer)):
        if not sentence.strip():
            continue
        body, pns = _strip_pns(sentence)
        cited = _cited_rows(pns, facts) if pns else []
        for q in extract_quantities(body):
            res.numbers_checked += 1
            present = any(_r(c) in facts.loose for c in q.cands)
            if not present:
                bad = q.raw
            elif q.unit and not _unit_ok(q.unit, q.cands, cited, facts):
                bad = f"{q.raw} {q.unit}"
            else:
                continue
            if bad not in flagged:
                flagged.add(bad)
                res.ungrounded.append(bad)
    return res
