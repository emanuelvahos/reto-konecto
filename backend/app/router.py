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

from app import acts
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
    r"\b(?:precios?|prices?|pricing|cuesta|cuestan|costs?|costos?|cotiz\w+|quote|presupuesto)\b",
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
_SIZE_LIKE = re.compile(r"(?<![A-Za-z0-9\-/.])\d{3}[A-Za-z]\d{2}(?![A-Za-z0-9\-/])")
_SIZE_TOKEN = re.compile(r"(?<![A-Za-z0-9])\d{3}[A-Za-z]\d{0,2}(?![A-Za-z0-9])")
# «763B», «763B00», «763 b 00», «761X30»: código de tamaño con sufijo opcional (00 / 30), se resuelve contra la base
_SIZE_REF = re.compile(
    r"(?<![A-Za-z0-9\-/])(?:(76[1-7])\s?([ABCXYabcxy])\s?(00|30)|(76[1-7])([ABCXYabcxy])|(76[1-7])\s([ABCXY]))(?![A-Za-z0-9])")
_SIZE_REF_KEY = re.compile(r"76[1-7][A-Z](?:00|30)?")

# --------------------------------------------------------------------------------------------- números de parte dictados
_SPOKEN = {
    "zero": "0", "cero": "0", "one": "1", "uno": "1", "two": "2", "dos": "2", "three": "3", "tres": "3", "four": "4", "cuatro": "4",
    "five": "5", "cinco": "5", "six": "6", "seis": "6", "seven": "7", "siete": "7", "eight": "8", "ocho": "8", "nine": "9", "nueve": "9",
    "dash": "-", "hyphen": "-", "guion": "-", "guión": "-", "menos": "-", "slash": "/", "barra": "/", "diagonal": "/",
    "equis": "X", "ex": "X", "x": "X", "ye": "Y", "why": "Y",
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
    r"qu[eé] (?:es|son|significa)\s+(?!(?:el|la|los|las|un|una|su|sus|esto|eso)\b)\w{2,}|what (?:is|are|does)\s+(?!(?:the|an?|it|its|their|this|that|these|those)\b)\w{2,}|\bdefin\w+|diferencia entre|difference between|expl[ií]c\w+|explain|"
    r"qu[eé] (?:es|son) (?:un |el |los )?actuador(?:es)?(?: el[eé]ctric\w+)?\b|what (?:is|are) (?:an? )?(?:electric )?actuators?\b|"
    r"c[oó]mo se calcula|how (?:is|are) .{0,30}calculated|tolerancia|tolerance|duty cycle|ciclo de trabajo|certificaciones|certifications|"
    r"(?:what is|qu[eé] es)\s+(?:the |la )?series?\s*76|"
    r"\bs4\b|clasificaci\w+|classification", FLAGS)
_CHOOSE_Q = re.compile(r"cu[aá]l (?:me )?(?:conviene|escojo|elijo|es mejor para m[ií])|which (?:one )?(?:should i (?:pick|choose|take|use)|is (?:best|better) for me)", FLAGS)
_COMPARE = re.compile(r"comp[aá]r\w+|versus|\bvs\.?\b|frente a|contra el|against", FLAGS)
_PRONOUN_REF = re.compile(r"\b(?:it|this one|that one|este|ese|esta|esa|[eé]ste|[eé]se|el anterior|la anterior|the previous|the same)\b|comp[aá]r[aá]l[oa]s?\b", FLAGS)
_FOLLOW_ALL = re.compile(r"comp[aá]r\w+|ambos|both|todos|\ball\b|\bboth\b|them|ellos", FLAGS)

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
    if "voltage_num" not in a:        # «762B00 de 220 monofasico», «a 110 single phase»: el voltaje va sin unidad pero junto a la fase
        m = re.search(r"(?<![\d.\-/])(24|110|220)(?![\d.%])\s*(?:,\s*)?(?:monof\w*|trif\w*|single|three|3\s?ph|1\s?ph|fase|phase)", text, FLAGS)
        if m:
            a["voltage_num"] = int(m.group(1))
    if "voltage_num" not in a:        # «hay antiexplosivos de 220?»: voltaje al final, sin unidad
        m = re.search(r"(?<![A-Za-z])(?:de|a|en|at|for|con)\s+(24|110|220)\s*[?.!]*\s*$", text, FLAGS)
        if m:
            a["voltage_num"] = int(m.group(1))
    if re.search(r"trif[aá]sic\w*|three[- ]?phase|\b3\s?[- ]?(?:ph|phase|fases?)\b|\b3\s?φ|\b3f\b", text, FLAGS):
        a["phase_type"] = "3 Phase"
    elif re.search(r"monof[aá]sic\w*|single[- ]?phase|\b1\s?[- ]?(?:ph|phase|fase)\b", text, FLAGS):
        a["phase_type"] = "Single Phase"
    if re.search(r"explosion[- ]?proof|antiexplos\w*|a prueba de explosi\w+|ex[- ]proof", text, FLAGS):
        a["enclosure_type"] = "Explosionproof"
    elif re.search(r"weather[- ]?proof|intemperie|exterior(?:es)?\b|outdoors?\b|al aire libre", text, FLAGS):
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
    for m in _SIZE_LIKE.finditer(text):       # «999Z00»: tiene forma de código de tamaño pero no existe -> el lookup responde INVALID_PART_NUMBER
        tok = m.group(0).upper()
        if pn_key(tok) not in known_keys and tok not in found and not any(tok in f for f in found):
            found.append(tok)
    for m in _SIZE_REF.finditer(text):
        tok = "".join(g for g in m.groups() if g).upper()
        if pn_key(tok[:4]) in known_keys and tok not in found and not any(tok[:4] in f.replace(" ", "") for f in found):
            found.append(tok)
    return found


@dataclass
class Decision:
    kind: str = "none"                 # "tools" | "reply" | "resolve" | "none"
    rule: str = "none"
    calls: List[Dict[str, Any]] = field(default_factory=list)   # [{"name", "args"}]
    reply: Optional[str] = None        # "out_of_scope" | "injection" | "ambiguous_size" | acto determinista (ver acts.py)
    clean_query: str = ""
    oos_note: bool = False             # consulta mixta: añadir nota determinista de fuera de alcance
    injection: bool = False
    out_of_scope: bool = False
    normalized: bool = False           # el número de parte dictado se convirtió a texto
    act: str = ""                      # acto identificado (telemetría): greeting, spec_lookup, recommend...
    attr_label: Optional[Dict[str, str]] = None   # atributo ausente del catálogo (etiqueta es/en)
    resolve: Dict[str, Any] = field(default_factory=dict)   # kind="resolve": {"what": "size_reference|next_size|previous_part", ...}


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


_SUPERLATIVE = re.compile(
    r"m[aá]s (?:potente|r[aá]pid\w*|lent\w*|peque\w*|grande|econ\w*|eficien\w*)|menos (?:consum\w*|gast\w*)|mayor (?:torque|potencia|par)|menor (?:consumo|torque|par)|"
    r"most powerful|fastest|slowest|smallest|biggest|largest|highest|lowest|least|strongest|more powerful", FLAGS)
_FOLLOW_CUE = re.compile(r"^\s*y\b|\bsu(?:s)?\b|\bits?\b|\bese\b|\besa\b|\beste\b|\besta\b|\bthat\b|\bthis\b|\bthe same\b|\bel mismo\b|\band\b", FLAGS)
_NEXT_SIZE = re.compile(r"siguiente tama[nñ]o|\bnext size\b|\bel siguiente\b|\bthe next one\b|tama[nñ]o (?:m[aá]s grande|mayor|superior)|bigger size|larger size|un tama[nñ]o (?:arriba|m[aá]s)", FLAGS)
_PREVIOUS = re.compile(r"\bel anterior\b|\bla anterior\b|\bthe previous(?: one)?\b|\bprevious one\b|\bel de antes\b|\bthe one before\b", FLAGS)
_AC_DC = re.compile(r"\bac\s?/?\s?-?\s?dc\b", FLAGS)
_DC = re.compile(r"\bdc\b|\bcc\b|corriente continua|direct current", FLAGS)


# --------------------------------------------------------------------------------------------- catálogo y ranking (SQL, sin LLM)
_ACT_VOCAB = re.compile(
    r"actuadores?|actuators?|motor(?:es)?|v[aá]lvulas?|valves?|torque|par|modelos?|models?|opci[oó]n(?:es)?|options?|series?|serie|planta|plant|aplicaci[oó]n|application|"
    r"proceso|process|damper|compuerta|gate|mariposa|butterfly|esfera|ball|voltaje|voltage|nm|fase|phase|intemperie|exterior|outdoor|zona|hazard|explos", FLAGS)
_CAT_SIZES = re.compile(r"qu[eé] tama[nñ]os|cu[aá]ntos tama[nñ]os|which sizes|what sizes|how many sizes|tama[nñ]os (?:hay|existen|manejan|tienen)|sizes (?:are|do you)", FLAGS)
_CAT_VOLTS = re.compile(r"qu[eé] (?:voltajes|tensiones)(?!.{0,25}toleranc)|cu[aá]les (?:son )?(?:los )?(?:voltajes|tensiones)|(?:voltajes|tensiones) (?:disponibles|manejan|hay|ofrecen|tienen)|(?:which|what) (?:supply )?voltages(?!.{0,25}toleranc)|voltages? (?:available|do you)", FLAGS)
_CAT_ENCL = re.compile(r"tipos? de carcasa|qu[eé] carcasas|(?:what|which) enclosures?|enclosure types?", FLAGS)
_CAT_PHASE = re.compile(r"tipos? de alimentaci[oó]n|qu[eé] alimentaciones|(?:what|which) (?:supply|power) types?|supply types?|qu[eé] fases", FLAGS)
_CAT_COUNT = re.compile(r"\bcu[aá]nt[oa]s\b|how many|n[uú]mero total de|total number of", FLAGS)
_CAT_EXISTS = re.compile(r"^\W*(?:hay|existen?|tienen|manejan|ofrecen|do you (?:have|offer)|are there|is there)\b", FLAGS)
_CAT_NOUN = re.compile(r"modelos?|actuadores?|variantes?|versiones|models?|actuators?|variants?|versions", FLAGS)
_CAT_DIFF = re.compile(r"diferenc\w+|difference|comp[aá]r\w+|compare|versus|\bvs\.?\b", FLAGS)
_BARE_SIZE = re.compile(r"(?<![A-Za-z0-9\-/.])(76[1-7])(?![A-Za-z0-9\-/])")

_RANK_RULES = [   # (patrón, métrica, sentido) en orden de especificidad
    (re.compile(r"m[aá]s potente|most powerful|strongest|mayor potencia|highest power|m[aá]s fuerte", FLAGS), "power", "max"),
    (re.compile(r"mayor (?:torque|par)\b|highest torque|torque (?:m[aá]s alto|m[aá]ximo)|m[aá]s torque|most torque|biggest torque", FLAGS), "torque", "max"),
    (re.compile(r"m[aá]s peque\w+|smallest|menor (?:torque|par)\b|lowest torque|least torque|menos torque", FLAGS), "torque", "min"),
    (re.compile(r"m[aá]s r[aá]pid\w+|fastest|quickest|menor tiempo|shortest (?:time|travel)|menos tiempo", FLAGS), "speed", "min"),
    (re.compile(r"m[aá]s lent\w+|slowest", FLAGS), "speed", "max"),
    (re.compile(r"menos (?:consum\w*|gast\w*|corriente|amper\w*)|least (?:current|power)|lowest (?:current|fla|consumption)|menor (?:consumo|corriente|fla)|m[aá]s eficien\w+|draws? the least|uses? the least", FLAGS), "fla", "min"),
    (re.compile(r"m[aá]s (?:consum\w*|gast\w*)|highest (?:current|fla|consumption)|draws? the most|mayor (?:consumo|corriente|fla)", FLAGS), "fla", "max"),
    (re.compile(r"mayor (?:ciclo|duty)|highest duty|m[aá]s ciclo", FLAGS), "duty", "max"),
]


def _catalog_filters(crit: Dict[str, Any]) -> Dict[str, Any]:
    return {k: crit[k] for k in ("voltage_num", "phase_type", "enclosure_type") if k in crit}


def catalog_decision(text: str, crit: Dict[str, Any], d: "Decision") -> Optional["Decision"]:
    """Preguntas sobre el catálogo (cuántos modelos, qué voltajes/tamaños/carcasas, diferencia entre dos tamaños)."""
    sizes = list(dict.fromkeys(_BARE_SIZE.findall(text)))
    if len(sizes) >= 2 and _CAT_DIFF.search(text):
        args = {"aspect": "compare_sizes", "sizes": [int(x) - 760 for x in sizes[:2]]}
    elif _CAT_COUNT.search(text) and (_CAT_VOLTS.search(text) or _CAT_ENCL.search(text) or _CAT_PHASE.search(text) or _CAT_SIZES.search(text)) and not _catalog_filters(crit):
        args = {"aspect": "summary"}      # pregunta compuesta («cuántos modelos hay y qué voltajes manejan»): el resumen responde ambas partes
    elif _CAT_SIZES.search(text):
        args = {"aspect": "sizes"}
    elif _CAT_VOLTS.search(text):
        args = {"aspect": "voltages"}
    elif _CAT_ENCL.search(text):
        args = {"aspect": "enclosures"}
    elif _CAT_PHASE.search(text):
        args = {"aspect": "phases"}
    elif _CAT_COUNT.search(text) and not any(k in crit for k in ("min_torque_nm", "min_torque_in_lbs", "max_speed_sec", "min_duty_cycle_pct", "max_fla_amps")):
        flt = _catalog_filters(crit)
        args = {"aspect": "count", **flt} if flt else {"aspect": "summary" if not _CAT_NOUN.search(text) else "count"}
    elif _CAT_EXISTS.search(text) and (_CAT_NOUN.search(text) or len(text.split()) <= 8) and _catalog_filters(crit) \
            and not any(k in crit for k in ("min_torque_nm", "min_torque_in_lbs", "max_speed_sec", "min_duty_cycle_pct", "max_fla_amps")):
        args = {"aspect": "count", **_catalog_filters(crit)}
    else:
        return None
    d.kind, d.rule, d.act = "tools", "catalog_overview", "catalog_overview"
    d.calls = [{"name": "catalog_overview", "args": args}]
    return d


def rank_decision(text: str, crit: Dict[str, Any], d: "Decision") -> Optional["Decision"]:
    """«el más potente», «el más rápido en 24V», «el que menos consume»: ranking por SQL con filtros duros opcionales."""
    for rx, metric, order in _RANK_RULES:
        if rx.search(text):
            d.kind, d.rule, d.act = "tools", "ranking", "ranking"
            d.calls = [{"name": "rank_actuators", "args": {"metric": metric, "order": order, **_catalog_filters(crit)}}]
            return d
    return None


def _size_ref_args(text: str, token: str, pending: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    crit = extract_criteria(text)
    phase = crit.get("phase_type")
    if not phase:
        phase = "AC/DC" if _AC_DC.search(text) else ("DC" if _DC.search(text) else None)
    ref = {"what": "size_reference", "size": pn_key(token)[:4], "voltage": crit.get("voltage_num"), "phase": phase,
           "focus": focus_groups(text), "frequency_hz": crit.get("frequency_hz")}
    if pending:                                  # respuesta a «¿qué alimentación?»: completa lo que faltaba
        ref["voltage"] = pending.get("voltage_num", ref["voltage"])
        ref["phase"] = pending.get("phase_type", ref["phase"])
    return ref


def route(query: str, active_parts: List[str], known_keys: Set[str], pending_args: Optional[Dict[str, Any]] = None,
          history_parts: Optional[List[str]] = None, size_pending: Optional[Dict[str, Any]] = None) -> Decision:
    query, d_spoken = normalize_spoken_pn(query)
    d = Decision(clean_query=query, normalized=d_spoken)
    rest, d.injection = _strip(query, _INJECTION)
    scope_text, oos = _strip(rest, _OUT_OF_SCOPE)
    d.out_of_scope = oos
    d.clean_query = rest or query

    if (d.injection or oos) and not _has_tech(scope_text if oos else rest, count_pn=not oos, known_keys=known_keys):
        d.kind, d.reply = "reply", ("injection" if d.injection and not oos else "out_of_scope")
        d.rule = "injection_only" if d.reply == "injection" else "out_of_scope"
        d.act = "off_topic" if d.reply == "injection" else "out_of_scope"
        return d
    d.oos_note = oos
    text = scope_text if oos else rest
    d.clean_query = text if (oos or d.injection) else query

    # Respuesta a «¿qué alimentación necesitas?» de una referencia de tamaño: se completa y se resuelve contra la base
    if size_pending:
        d.kind, d.rule, d.act = "resolve", "size_reference", "spec_lookup"
        d.resolve = _size_ref_args(text, size_pending["size_code"], size_pending)
        return d

    pns = find_part_numbers(text, known_keys)
    crit0 = extract_criteria(text)
    # contenido técnico duro (la palabra suelta «datos» o «ficha» no basta: «qué datos manejas» es una pregunta de capacidades)
    tech = bool(pns or any(k in crit0 for k in _NUMERIC_CRITERIA) or _RECO_VERB.search(text) or _CONCEPT.search(text) or focus_groups(text))

    # ---------------------------------------------------------------- actos conversacionales (sin LLM, sin herramientas)
    if not tech:
        act = acts.detect_conversational(text)
        if act:
            d.kind, d.reply, d.rule, d.act = "reply", act, f"act:{act}", act
            return d
    if not pns and not _SPEC_GENERIC.search(text) and not _RECO_VERB.search(text) and not focus_groups(text)             and (_CAT_COUNT.search(text) or _CAT_SIZES.search(text)) and (cd0 := catalog_decision(text, crit0, d)) is not None:
        return cd0          # «cuántas versiones hay en total» no es una pregunta por un atributo ausente aunque diga «big»/«grande»
    if not _SPEC_GENERIC.search(text) and not _RECO_VERB.search(text) and not focus_groups(text):
        attr = acts.detect_attribute(text)
        if attr:
            d.kind, d.reply, d.rule, d.act, d.attr_label = "reply", "attribute", "act:attribute", "out_of_catalog_attribute", attr
            return d
    if acts.is_application_context(text) and not pns and "min_torque_nm" not in crit0 and "min_torque_in_lbs" not in crit0:
        d.kind, d.reply, d.rule, d.act = "reply", "application", "act:application", "application_context"
        return d

    if not pns and (cd := catalog_decision(text, crit0, d)) is not None and cd.calls[0]["args"].get("aspect") == "compare_sizes":
        return cd

    if pns:
        groups = focus_groups(text)
        hz = crit0.get("frequency_hz")
        d.kind, d.rule, d.act = "tools", "part_number", "spec_lookup"
        size_refs = [p for p in pns if _SIZE_REF_KEY.fullmatch(pn_key(p))]
        if size_refs and len(pns) >= 2:
            # «761A00 con el 762A00 de 110V»: cada código de tamaño se resuelve contra la base con la alimentación dicha
            ref = _size_ref_args(text, size_refs[0])
            d.kind, d.rule = "resolve", "size_references"
            d.resolve = {"what": "size_references", "pns": pns[:3], "voltage": ref["voltage"], "phase": ref["phase"],
                         "focus": groups, "frequency_hz": hz, "compare": bool(_COMPARE.search(text))}
            return d
        if len(pns) == 1 and size_refs and not _COMPARE.search(text):
            # «763B00», «763 b 00 de 110 voltios»: se resuelve contra la base (un modelo -> ficha; varios -> opciones reales)
            d.kind, d.rule = "resolve", "size_reference"
            d.resolve = _size_ref_args(text, pns[0])
            return d
        if active_parts and _COMPARE.search(text) and _PRONOUN_REF.search(text):
            keys = {pn_key(x) for x in pns}
            pns = [a for a in active_parts[:1] if pn_key(a) not in keys] + pns
        d.act = "compare" if len(pns) >= 2 and _COMPARE.search(text) else "spec_lookup"
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
        d.kind, d.rule, d.act = "tools", "pending_clarification", "recommend"
        d.calls = [{"name": "recommend_actuators", "args": {}}]
        return d

    crit = crit0
    if not any(k in crit for k in ("min_torque_nm", "min_torque_in_lbs")):
        if (rd := rank_decision(text, crit, d)) is not None:
            return rd
        if (cd := catalog_decision(text, crit, d)) is not None:
            return cd
    if (_RECO_VERB.search(text) and not any(k in crit for k in _NUMERIC_CRITERIA) and len(text.split()) >= 4
            and not _ACT_VOCAB.search(text) and not crit):
        d.rule, d.act = "uncertain", "unclear"     # «recomiéndame una película»: un verbo de selección sin nada de actuadores lo decide el clasificador
        return d
    if any(k in crit for k in _NUMERIC_CRITERIA) or (_RECO_VERB.search(text) and not _SUPERLATIVE.search(text)):
        d.kind, d.rule, d.act = "tools", "selection_criteria", "recommend"
        d.calls = [{"name": "recommend_actuators", "args": crit}]
        return d

    if _CONCEPT.search(text):
        d.kind, d.rule, d.act = "tools", "concept", "knowledge"
        d.calls = [{"name": "search_engineering_knowledge", "args": {"query": text}}]
        return d

    if _SUPERLATIVE.search(text):          # «el más potente»: no es un seguimiento de la parte activa (lo atiende el clasificador)
        d.rule, d.act = "uncertain", "ranking"
        return d

    if active_parts and _NEXT_SIZE.search(text):
        d.kind, d.rule, d.act = "resolve", "next_size", "spec_lookup"
        d.resolve = {"what": "next_size", "focus": focus_groups(text), "frequency_hz": crit.get("frequency_hz")}
        return d

    if _PREVIOUS.search(text) and (focus_groups(text) or _SPEC_GENERIC.search(text) or history_parts):
        if history_parts:
            groups = focus_groups(text)
            args = {"part_number": history_parts[0], **({"focus": groups} if groups else {})}
            d.kind, d.rule, d.act = "tools", "previous_part", "spec_lookup"
            d.calls = [{"name": "lookup_actuator_by_part_number", "args": args}]
            return d

    if active_parts and (focus_groups(text) or _SPEC_GENERIC.search(text)):
        groups = focus_groups(text)
        hz = crit.get("frequency_hz")
        parts = active_parts[:3] if _FOLLOW_ALL.search(text) else active_parts[:1]
        d.kind, d.rule, d.act = "tools", "followup_active_part", "spec_lookup"
        for pn in parts:
            args = {"part_number": pn}
            if groups:
                args["focus"] = groups
            if hz:
                args["frequency_hz"] = hz
            d.calls.append({"name": "lookup_actuator_by_part_number", "args": args})
        return d

    if _CHOOSE_Q.search(text) and not pns and not crit0 and len(text.split()) <= 8:
        d.kind, d.reply, d.rule, d.act = "reply", "ask_criteria", "act:ask_criteria", "clarify"     # «¿cuál me conviene?» sin criterios: se pregunta el criterio
        return d

    if _COMPARE.search(text) and not pns and len(text.split()) <= 8:
        pair = list(dict.fromkeys(active_parts[:1] + (history_parts or [])[:1]))
        if len(pair) >= 2:                  # «compáralos»: el modelo activo y el anterior de la conversación
            d.kind, d.rule, d.act = "tools", "compare_previous", "compare"
            d.calls = [{"name": "lookup_actuator_by_part_number", "args": {"part_number": pn}} for pn in pair]
            return d
        d.kind, d.reply, d.rule, d.act = "reply", "clarify_which", "act:clarify_which", "compare"
        return d

    if (not active_parts and (focus_groups(text) or _SPEC_GENERIC.search(text)) and _FOLLOW_CUE.search(text) and len(text.split()) <= 8
            and not re.search(r"\bqu[eé] (?:es|son)\b|\bwhat (?:is|are)\b|\bdime\b", text, FLAGS)):
        # «cuánto tarda ese?» sin ningún modelo en la conversación: se pregunta de cuál, no se elige uno
        d.kind, d.reply, d.rule, d.act = "reply", "clarify_which", "act:clarify_which", "spec_lookup"
        return d

    d.rule = "uncertain"
    d.act = "unclear"
    return d
