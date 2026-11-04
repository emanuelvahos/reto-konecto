"""Verificador numerico (REGLA 4: ningun numero que vea el usuario puede venir del LLM).

verify_answer() extrae todos los numeros de la respuesta final y comprueba que cada uno exista en:
  - las salidas de herramientas de ESTE turno (incluye conversiones ya presentes, p. ej. Nm e in-lbs),
  - el mensaje del usuario,
  - las excepciones declaradas en config/verifier.json (marcadores de lista, "90°").
Los numeros de parte se validan aparte: deben existir en la base de datos o ser eco textual del usuario.
Es una funcion pura (sin red ni DB): los numeros de parte conocidos llegan por parametro.
"""
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "verifier.json"

# Numero de parte completo (con guion) o codigo de tamano (761A, 766A00)
PN_RE = re.compile(r"\b76\d[A-Za-z0-9]{0,4}-[A-Za-z0-9]{4,9}(?:/[A-Za-z])?|\b76\d[A-Za-z]\d{0,2}\b", re.IGNORECASE)
# Token numerico: sin letras/digitos pegados por la izquierda (descarta T4, S4, IIB...)
NUM_RE = re.compile(r"(?<![A-Za-z0-9_])\d+(?:[.,  ]\d+)*")
LIST_MARKER_RE = re.compile(r"(?m)^\s*\d{1,2}[.)]\s")
PRECISION = 6


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
    tok = token.replace(" ", "").replace(" ", "")
    parts = re.split(r"[.,]", tok)
    if len(parts) == 1:
        return [float(tok)]
    cands: List[float] = []
    if len(parts) == 2:
        cands.append(float(parts[0] + "." + parts[1]))
    if all(len(p) == 3 for p in parts[1:]) and 1 <= len(parts[0]) <= 3:
        cands.append(float("".join(parts)))
    return cands or [float(p) for p in parts]


def extract_numbers(text: str, apply_exceptions: bool = False) -> List[Tuple[str, List[float]]]:
    """[(texto_del_token, [valores candidatos])] ignorando numeros de parte (se validan aparte)."""
    body, _ = _strip_pns(text)
    if apply_exceptions:
        cfg = _config()
        if cfg.get("skip_list_markers"):
            body = LIST_MARKER_RE.sub(" ", body)
        for pat in cfg.get("free_patterns", []):
            body = re.sub(pat, " ", body, flags=re.IGNORECASE)
    return [(m.group(0), _candidates(m.group(0))) for m in NUM_RE.finditer(body)]


def _walk_numbers(obj: Any, out: Set[float]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        out.add(round(float(obj), PRECISION))
    elif isinstance(obj, str):
        for _, cands in extract_numbers(obj):
            out.update(round(c, PRECISION) for c in cands)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            # los nombres de campo llevan la frecuencia (fla_60hz_amps): "60 Hz" está respaldado por el campo
            out.update(float(n) for n in re.findall(r"(\d+)hz", str(k).lower()))
            _walk_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_numbers(v, out)


def allowed_numbers(tool_outputs: Iterable[Any], user_message: str) -> Set[float]:
    allowed: Set[float] = set()
    for out in tool_outputs:
        _walk_numbers(out, allowed)
    _walk_numbers(user_message, allowed)
    return allowed


def verify_answer(
    answer: str,
    tool_outputs: Iterable[Any],
    user_message: str,
    known_parts: Set[str],
) -> VerificationResult:
    allowed = allowed_numbers(tool_outputs, user_message)
    user_pns = {pn_key(p) for p in PN_RE.findall(user_message)}
    res = VerificationResult()

    _, answer_pns = _strip_pns(answer)
    for pn in dict.fromkeys(answer_pns):
        res.numbers_checked += 1
        k = pn_key(pn)
        if k not in known_parts and k not in user_pns:
            res.ungrounded.append(f"PN:{pn.upper()}")

    for raw, cands in extract_numbers(answer, apply_exceptions=True):
        res.numbers_checked += 1
        if not any(round(c, PRECISION) in allowed for c in cands) and raw not in res.ungrounded:
            res.ungrounded.append(raw)
    return res
