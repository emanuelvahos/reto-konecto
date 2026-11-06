"""Router determinista (sin LLM) que decide ANTES del agente qué herramienta hay que llamar o si la consulta está fuera de alcance.

Reglas (es/en), en este orden:
  1. Inyección de prompt / "ignora las herramientas", "responde de memoria", "muestra tu prompt": se recorta de la consulta
     que verá el LLM. Si no queda consulta técnica -> respuesta determinista (reply "injection").
  2. Fuera de alcance (precio, plazo de entrega, stock, descuento, garantía, otras marcas): si no queda consulta técnica
     (un numero de parte solo NO cuenta como consulta tecnica) -> respuesta determinista (reply "out_of_scope"); si queda,
     se atiende esa parte y se anade una nota determinista.
  3. Numero de parte (tolerante a typos, con o sin sufijo) -> lookup_actuator_by_part_number (uno por numero de parte).
  4. Respuesta a una aclaracion pendiente -> recommend_actuators (la herramienta completa los argumentos pendientes).
  5. Criterios de seleccion numericos o verbo de seleccion -> recommend_actuators con argumentos extraidos por reglas.
  6. Pregunta conceptual -> search_engineering_knowledge.
  7. Seguimiento de especificaciones con partes activas en la sesion -> lookup de la parte activa.
  8. Si no hay certeza -> kind="none": el agente decide con el LLM (camino anterior).

No hay valores de catalogo escritos a mano: los codigos de tamano validos llegan por parametro (leidos de la base) y los
valores de voltaje, torque, etc. se extraen del propio mensaje (la herramienta valida contra el catalogo).
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from app.fallback import _GROUP_KEYWORDS
from app.verifier import pn_key

FLAGS = re.IGNORECASE | re.UNICODE

# --------------------------------------------------------------------------------------------- inyección
_INJECTION = [re.compile(p, FLAGS) for p in (
    r"\b(?:ignor\w*|olvid\w*|omit\w*|forget|disregard|skip|bypass|salt\w*)\b[^.?!\n:;]{0,40}?\b(?:herramientas|tools?|instrucciones|instructions|reglas|rules|prompt|restricciones|guardrails|sistema|system)\b",
    r"\b(?:responde|contesta|answer|reply|respond|dime|tell me)\b[^.?!\n:;]{0,30}?\b(?:de memoria|from memory|sin (?:usar |utilizar )?(?:las |tus )?herramientas|without (?:using )?(?:any |the )?tools?)\b",
    r"\b(?:de memoria|from memory|from your memory|desde tu memoria)\b",
    r"\b(?:sin|without)\s+(?:usar\s+|utilizar\s+|using\s+)?(?:las\s+|tus\s+|any\s+|the\s+)?(?:herramientas|tools?)\b",
    r"\b(?:no|do not|don't)\s+(?:uses?|utilices?|use)\s+(?:las |tus |any |the )?(?:herramientas|tools?)\b",
    r"\b(?:muestra|mu[eé]strame|show|reveal|print|repite|repeat|revela|imprime|dame|give me)\b[^.?!\n:;]{0,25}?\b(?:tu|your|el|the)\s+(?:(?:system|sistema|hidden|secret|oculta?s?|ocultas?|internal|internas?)\s+)*(?:prompt|instrucciones|instructions)\b",
    r"\b(?:you are now|from now on,? you|ahora eres|a partir de ahora)\b[^.?!\n]{0,80}",
    r"\b(?:developer mode|modo desarrollador|jailbreak|sin restricciones|no restrictions|without restrictions)\b[^.?!\n]*",
    r"\b(?:invent\w*|make up|fabricate|fabrica)\b[^.?!\n]{0,40}?\b(?:valor|value|dato|data|cifra|number|n[uú]mero|torque)\b[^.?!\n]*",
    r"\b(?:responde|contesta|answer|reply|respond|say|di|escribe|write|a[nñ]ade|add|append|termina|end)\b[^.?!\n]{0,25}?['\"“‘«][^'\"”’»]{1,40}['\"”’»](?:\s+(?:al final|al inicio|at the end|at the start|at the beginning))?",
)]

# --------------------------------------------------------------------------------------------- fuera de alcance
_OUT_OF_SCOPE = [re.compile(p, FLAGS) for p in (
    r"\b(?:precios?|prices?|pricing|cuest\w+|costs?|costos?|cotizaci\w+|quote|presupuesto)\b",
    r"\b(?:plazos?\s+de\s+entrega|tiempos?\s+de\s+entrega|lead[- ]?times?|delivery\s+(?:time|date)s?|fecha\s+de\s+entrega|shipping|env[ií]o)\b",
    r"\b(?:stock|en existencia|inventario|inventory|in stock)\b",
    r"\b(?:descuentos?|discounts?|promoci[oó]n|promotion)\b",
    r"\b(?:garant[ií]as?|warranty|warranties)\b",
    r"\b(?:otras marcas|other brands?|competidor\w*|competitors?|rotork|auma|limitorque|emerson|bray|flowserve)\b",
)]

# --------------------------------------------------------------------------------------------- número de parte
_PN_TOKEN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{5,7}\s?-\s?[A-Za-z0-9]{6,9}(?:\s?/\s?[A-Za-z])?(?![A-Za-z0-9])")
_PN_SPACED = re.compile(r"(?<![A-Za-z0-9])\d{3}[A-Za-z0-9]{2,4}[\s.]+\d[A-Za-z0-9]{5,8}(?:\s?/\s?[A-Za-z])?(?![A-Za-z0-9])")
_PN_FLAT = re.compile(r"(?<![A-Za-z0-9])\d[A-Za-z0-9]{3,6}\d{5,8}[A-Za-z0-9]?/?[A-Za-z]?(?![A-Za-z0-9])")
_SIZE_ONLY = re.compile(r"76\d[A-Z]")
_SIZE_TOKEN = re.compile(r"(?<![A-Za-z0-9])\d{3}[A-Za-z]\d{0,2}(?![A-Za-z0-9])")

# --------------------------------------------------------------------------------------------- números de parte dictados
_SPOKEN = {
    "zero": "0", "cero": "0", "one": "1", "uno": "1", "two": "2", "dos": "2", "three": "3", "tres": "3", "four": "4", "cuatro": "4",
    "five": "5", "cinco": "5", "six": "6", "seis": "6", "seven": "7", "siete": "7", "eight": "8", "ocho": "8", "nine": "9", "nueve": "9",
    "dash": "-", "hyphen": "-", "guion": "-", "guión": "-", "menos": "-", "slash": "/", "barra": "/", "diagonal": "/",
    "a": "A", "ay": "A", "b": "B", "be": "B", "bee": "B", "c": "C", "ce": "C", "see": "C", "sea": "C",
}
_SPOKEN_DIGITS = {k for k, v in _SPOKEN.items() if v.isdigit()}


def normalize_spoken_pn(text: str) -> (str, bool):
    """Convierte un número de parte dictado ("siete seis tres be cero cero guion uno uno ... barra a") al número escrito.
    Solo actúa sobre rachas de palabras de dígito/letra/guion/barra con al menos 8 palabras de dígito (no toca prosa normal)."""
    toks = list(re.finditer(r"[^\s,;]+", text))
    out, i, changed = [], 0, False
    last_end = 0
    while i < len(toks):
        j, syms, digits = i, [], 0
        while j < len(toks):
            w = re.sub(r"^[^\wáéíóúñ]+|[^\wáéíóúñ]+$", "", toks[j].group(0).lower())
            if w in _SPOKEN:
                syms.append(_SPOKEN[w])
                digits += w in _SPOKEN_DIGITS
                j += 1
            else:
                break
        if digits >= 8 and "-" in syms:
            out.append(text[last_end:toks[i].start()])
            out.append("".join(syms))
            last_end = toks[j - 1].end()
            changed = True
            i = j
        else:
            i = max(j, i + 1)
    out.append(text[last_end:])
    return "".join(out), changed


# --------------------------------------------------------------------------------------------- tipo de consulta
_SPEC = {**_GROUP_KEYWORDS}
_SPEC_GENERIC = re.compile(r"especificaci|specs?\b|specification|ficha|datos|datasheet|data sheet|detalles|details|csa|certific|hz\b", FLAGS)
_RECO_VERB = re.compile(
    r"recomi\w+|recommend\w*|suger\w+|suggest\w*|selecci\w+|\bselect\w*|\belegir\b|\bchoose\b|escoger|"
    r"necesito (?:un |una |el )?actuador|i need (?:an? |the )?actuator|\bbusco\b|looking for|quiero (?:un |una )?actuador|"
    r"which actuator|what actuator|qu[eé] actuador|cu[aá]l actuador|best actuator|mejor actuador|help me (?:select|choose|pick)|"
    r"actuator (?:for|that|which|with)|actuador (?:para|que|con)", FLAGS)
_CONCEPT = re.compile(
    r"qu[eé] (?:es|son|significa)\s+(?!(?:el|la|los|las|un|una|su|sus|esto|eso)\b)\w{2,}|what (?:is|are|does)\s+(?!(?:the|an?|it|its|their|this|that|these|those)\b)\w{2,}|\bdefin\w+|diferencia entre|difference between|explica\w*|explain|"
    r"c[oó]mo se calcula|how (?:is|are) .{0,30}calculated|tolerancia|tolerance|duty cycle|ciclo de trabajo|certificaciones|certifications|"
    r"\bs4\b|clasificaci\w+|classification", FLAGS)
_COMPARE = re.compile(r"compar\w+|versus|\bvs\.?\b|frente a|contra el|against", FLAGS)
_PRONOUN_REF = re.compile(r"\b(?:it|this one|that one|este|ese|esta|esa|[eé]ste|[eé]se|el anterior|la anterior|the previous|the same)\b", FLAGS)
_FOLLOW_ALL = re.compile(r"compar\w+|ambos|both|todos|\ball\b|\bboth\b|them|ellos", FLAGS)

_NUM = r"(\d[\d.,   ]*\d|\d)"


def _to_float(s: str) -> float:
    t = re.sub(r"(?<=\d)[,   ](?=\d{3}\b)", "", s)
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    return float(t)


def extract_criteria(text: str) -> Dict[str, Any]:
    """Argumentos de recommend_actuators por reglas (el LLM no interviene)."""
    a: Dict[str, Any] = {}
    m = re.search(_NUM + r"\s*(?:nm|n\s?[·.\-]?\s?m|newton[- ]?(?:metros?|meters?))\b", text, FLAGS)
    if m:
        a["min_torque_nm"] = _to_float(m.group(1))
    else:
        m = re.search(_NUM + r"\s*(?:in\.?\s?[-·]?\s?lbs?|lb\s?-?\s?in|libras?[- ]pulgadas?)", text, FLAGS)
        if m:
            a["min_torque_in_lbs"] = _to_float(m.group(1))
    m = re.search(r"(?<![\d.])(\d{2,3})\s?(?:v\b|vac\b|vdc\b|volts?\b|voltios?\b)", text, FLAGS)
    if m:
        a["voltage_num"] = int(m.group(1))
    if re.search(r"trif[aá]sic\w*|three[- ]?phase|\b3\s?[- ]?(?:ph|phase|fases?)\b|\b3\s?φ", text, FLAGS):
        a["phase_type"] = "3 Phase"
    elif re.search(r"monof[aá]sic\w*|single[- ]?phase|\b1\s?[- ]?(?:ph|phase|fase)\b", text, FLAGS):
        a["phase_type"] = "Single Phase"
    if re.search(r"explosion[- ]?proof|antiexplos\w*|a prueba de explosi\w+|ex[- ]proof", text, FLAGS):
        a["enclosure_type"] = "Explosionproof"
    elif re.search(r"weather[- ]?proof|intemperie", text, FLAGS):
        a["enclosure_type"] = "Weatherproof"
    neg = re.search(r"\bno\s+(?:es\s+|est[aá]\s+)?(?:un[ao]?\s+)?(?:[aá]rea\s+|zona\s+)?peligros\w*|non[- ]?hazard\w*|not\s+(?:a\s+)?hazard\w*|[aá]rea segura|safe area", text, FLAGS)
    if neg:
        a["hazardous_area"] = False
    elif re.search(r"peligros\w*|hazardous|explosiv\w*|clasificad\w*|classified|\batex\b|class\s*i\b|clase\s*i\b|zona\s+\d|zone\s+\d", text, FLAGS):
        a["hazardous_area"] = True
    if re.search(r"modul\w*", text, FLAGS):
        a["application_type"] = "Modulating"
    elif re.search(r"on\s*/?\s*-?\s*off", text, FLAGS):
        a["application_type"] = "On/Off"
    m = re.search(r"(?:menos de|under|less than|within|en menos de|m[aá]xim\w+|max(?:imum)?|hasta|up to|<)\s*" + _NUM + r"\s*(?:s\b|sec\w*|seg\w*|seconds?)", text, FLAGS)
    if m:
        a["max_speed_sec"] = _to_float(m.group(1))
    m = re.search(r"(?:duty|ciclo|s4)[^\d]{0,25}" + _NUM + r"\s*%", text, FLAGS)
    if m:
        a["min_duty_cycle_pct"] = int(_to_float(m.group(1)))
    m = re.search(r"(?:fla|corriente|current)[^\d.]{0,30}(?:menos de|under|less than|m[aá]xim\w+|max(?:imum)?|<)\s*" + _NUM + r"\s*(?:a\b|amps?|amperes?|amperios?)", text, FLAGS)
    if m:
        a["max_fla_amps"] = _to_float(m.group(1))
    if re.search(r"\bcsa\b", text, FLAGS) and re.search(r"must|debe|requier\w+|require\w*|exig\w+|obligator\w+|certified|certificad\w+", text, FLAGS):
        a["require_csa_certification"] = True
    m = re.search(r"(?:factor de (?:seguridad|servicio)|margen de seguridad|safety (?:factor|margin)|service factor)\D{0,14}(\d+(?:[.,]\d+)?)\s?(%?)", text, FLAGS)
    if m:
        v = _to_float(m.group(1))
        f = 1 + v / 100 if m.group(2) else v
        if 1.0 < f <= 5.0:
            a["safety_factor"] = round(f, 4)
    hz = set(re.findall(r"(?<![\d.])(\d{2})\s?hz\b", text, FLAGS))
    if len(hz) == 1:
        a["frequency_hz"] = int(next(iter(hz)))
    return a


_NUMERIC_CRITERIA = ("min_torque_nm", "min_torque_in_lbs", "voltage_num", "max_speed_sec", "min_duty_cycle_pct", "max_fla_amps")


def focus_groups(text: str) -> List[str]:
    return [g for g, pat in _SPEC.items() if re.search(pat, text, FLAGS)]


def find_part_numbers(text: str, known_keys: Set[str]) -> List[str]:
    """Tokens que parecen numero de parte (hasta con typos 0/O, 8/B) o codigos de tamaño conocidos."""
    found: List[str] = []
    for rx in (_PN_TOKEN, _PN_SPACED, _PN_FLAT):
        for m in rx.finditer(text):
            tok = re.sub(r"\s", "", m.group(0)).upper()
            if rx is _PN_SPACED:
                h, t2 = re.split(r"[\s.]+", m.group(0).strip().upper(), maxsplit=1)
                tok = h + "-" + re.sub(r"\s", "", t2)
            if tok not in found:
                found.append(tok)
    for m in _SIZE_TOKEN.finditer(text):
        tok = m.group(0).upper()
        if pn_key(tok) in known_keys and tok not in found and not any(tok in f for f in found):
            found.append(tok)
    return found


@dataclass
class Decision:
    kind: str = "none"                 # "tools" | "reply" | "none"
    rule: str = "none"
    calls: List[Dict[str, Any]] = field(default_factory=list)   # [{"name", "args"}]
    reply: Optional[str] = None        # "out_of_scope" | "injection"
    clean_query: str = ""
    oos_note: bool = False             # consulta mixta: añadir nota determinista de fuera de alcance
    injection: bool = False
    out_of_scope: bool = False
    normalized: bool = False           # el número de parte dictado se convirtió a texto


def _strip(text: str, patterns) -> (str, bool):
    hit = False
    for rx in patterns:
        new = rx.sub(" ", text)
        if new != text:
            hit = True
            text = new
    text = re.sub(r"\s{2,}", " ", text).strip(" \t,;:-—")
    return text, hit


def _has_tech(text: str, count_pn: bool, known_keys: Set[str]) -> bool:
    if count_pn and find_part_numbers(text, known_keys):
        return True
    c = extract_criteria(text)
    return bool(
        focus_groups(text) or _SPEC_GENERIC.search(text) or _RECO_VERB.search(text) or _CONCEPT.search(text)
        or any(k in c for k in _NUMERIC_CRITERIA)
    )


def route(query: str, active_parts: List[str], known_keys: Set[str], pending_args: Optional[Dict[str, Any]] = None) -> Decision:
    query, d_spoken = normalize_spoken_pn(query)
    d = Decision(clean_query=query, normalized=d_spoken)
    rest, d.injection = _strip(query, _INJECTION)
    scope_text, oos = _strip(rest, _OUT_OF_SCOPE)
    d.out_of_scope = oos
    d.clean_query = rest or query

    if (d.injection or oos) and not _has_tech(scope_text if oos else rest, count_pn=not oos, known_keys=known_keys):
        d.kind, d.reply = "reply", ("injection" if d.injection and not oos else "out_of_scope")
        d.rule = "injection_only" if d.reply == "injection" else "out_of_scope"
        return d
    d.oos_note = oos
    text = scope_text if oos else rest
    d.clean_query = text if (oos or d.injection) else query

    pns = find_part_numbers(text, known_keys)
    if pns:
        groups = focus_groups(text)
        hz = extract_criteria(text).get("frequency_hz")
        d.kind, d.rule = "tools", "part_number"
        if active_parts and _COMPARE.search(text) and _PRONOUN_REF.search(text):
            keys = {pn_key(x) for x in pns}
            pns = [a for a in active_parts[:1] if pn_key(a) not in keys] + pns
        if len(pns) >= 2 and _COMPARE.search(text) and any(_SIZE_ONLY.fullmatch(pn_key(x)) for x in pns):
            # «763B y 763C»: un código de tamaño agrupa varias alimentaciones; comparar sin elegir mostraría modelos que
            # el usuario no nombró. Se pide el número de parte completo o la alimentación (respuesta fija, sin cifras).
            d.kind, d.rule, d.reply, d.calls = "reply", "ambiguous_size", "ambiguous_size", []
            return d
        for pn in pns[:3]:
            args: Dict[str, Any] = {"part_number": pn}
            if groups:
                args["focus"] = groups
            if hz:
                args["frequency_hz"] = hz
            d.calls.append({"name": "lookup_actuator_by_part_number", "args": args})
        return d

    if pending_args:
        d.kind, d.rule = "tools", "pending_clarification"
        d.calls = [{"name": "recommend_actuators", "args": {}}]
        return d

    crit = extract_criteria(text)
    if any(k in crit for k in _NUMERIC_CRITERIA) or _RECO_VERB.search(text):
        d.kind, d.rule = "tools", "selection_criteria"
        d.calls = [{"name": "recommend_actuators", "args": crit}]
        return d

    if _CONCEPT.search(text):
        d.kind, d.rule = "tools", "concept"
        d.calls = [{"name": "search_engineering_knowledge", "args": {"query": text}}]
        return d

    if active_parts and (focus_groups(text) or _SPEC_GENERIC.search(text)):
        groups = focus_groups(text)
        hz = crit.get("frequency_hz")
        parts = active_parts[:3] if _FOLLOW_ALL.search(text) else active_parts[:1]
        d.kind, d.rule = "tools", "followup_active_part"
        for pn in parts:
            args = {"part_number": pn}
            if groups:
                args["focus"] = groups
            if hz:
                args["frequency_hz"] = hz
            d.calls.append({"name": "lookup_actuator_by_part_number", "args": args})
        return d

    d.rule = "uncertain"
    return d
