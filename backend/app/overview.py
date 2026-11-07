"""Textos deterministas (es/en) para las herramientas catalog_overview y rank_actuators.

Cada cifra sale de la salida de la herramienta del turno (SQL); nada se escribe a mano ni lo redacta el LLM.
Los textos del ranking dicen qué métrica y qué filtros se usaron y que solo cuentan los modelos disponibles.
"""
from typing import Any, Dict, List

from app.fallback import _fmt

PHASE = {"Single Phase": {"en": "single-phase", "es": "monofásicos"}, "3 Phase": {"en": "three-phase", "es": "trifásicos"},
         "AC/DC": {"en": "AC/DC", "es": "AC/DC"}, "DC": {"en": "DC", "es": "DC"}}
ENCLOSURE = {"Weatherproof": {"en": "Weatherproof", "es": "Weatherproof"}, "Explosionproof": {"en": "Explosionproof (hazardous areas)", "es": "Explosionproof (zonas clasificadas)"}}

METRIC = {   # (métrica, sentido) -> (nombre del criterio, etiqueta del resultado)
    ("torque", "max"): {"en": ("highest torque", "the highest torque"), "es": ("mayor torque", "el mayor torque")},
    ("torque", "min"): {"en": ("lowest torque", "the lowest torque"), "es": ("menor torque", "el menor torque")},
    ("power", "max"): {"en": ("highest motor power", "the highest motor power"), "es": ("mayor potencia de motor", "la mayor potencia de motor")},
    ("power", "min"): {"en": ("lowest motor power", "the lowest motor power"), "es": ("menor potencia de motor", "la menor potencia de motor")},
    ("speed", "min"): {"en": ("fastest (fewest seconds per 90° turn)", "the shortest travel time"), "es": ("más rápido (menos segundos por giro de 90°)", "el menor tiempo de giro")},
    ("speed", "max"): {"en": ("slowest (most seconds per 90° turn)", "the longest travel time"), "es": ("más lento (más segundos por giro de 90°)", "el mayor tiempo de giro")},
    ("fla", "min"): {"en": ("lowest full-load current (FLA)", "the lowest FLA"), "es": ("menor corriente a plena carga (FLA)", "la menor FLA")},
    ("fla", "max"): {"en": ("highest full-load current (FLA)", "the highest FLA"), "es": ("mayor corriente a plena carga (FLA)", "la mayor FLA")},
    ("lra", "min"): {"en": ("lowest locked-rotor current (LRA)", "the lowest LRA"), "es": ("menor corriente de rotor bloqueado (LRA)", "la menor LRA")},
    ("lra", "max"): {"en": ("highest locked-rotor current (LRA)", "the highest LRA"), "es": ("mayor corriente de rotor bloqueado (LRA)", "la mayor LRA")},
    ("duty", "max"): {"en": ("highest duty cycle (S4)", "the highest S4 duty"), "es": ("mayor ciclo de trabajo (S4)", "el mayor ciclo S4")},
    ("duty", "min"): {"en": ("lowest duty cycle (S4)", "the lowest S4 duty"), "es": ("menor ciclo de trabajo (S4)", "el menor ciclo S4")},
}


def _filters_text(filters: Dict[str, Any], lang: str) -> str:
    bits: List[str] = []
    if filters.get("voltage_num") is not None:
        bits.append(f"{filters['voltage_num']} V")
    if filters.get("phase_type") in PHASE:
        bits.append(PHASE[filters["phase_type"]][lang])
    if filters.get("enclosure_type") in ENCLOSURE:
        bits.append(ENCLOSURE[filters["enclosure_type"]][lang])
    return ", ".join(bits)


def _short(word: str) -> str:
    return word.split(" (")[0]


def _join(items: List[str], lang: str) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + (" y " if lang == "es" else " and ") + items[-1]


def render_rank(out: Dict[str, Any], lang: str) -> str:
    status = out.get("status")
    flt = _filters_text(out.get("filters") or {}, lang)
    if status != "RANKED":
        if status == "RANK_NO_DATA":
            return ("No hay modelos disponibles con ese dato" + (f" para {flt}" if flt else "") + " en el catálogo." if lang == "es"
                    else "There are no available models with that data" + (f" for {flt}" if flt else "") + " in the catalog.")
        return "No pude consultar el catálogo ahora mismo. Inténtalo de nuevo." if lang == "es" else "I couldn't query the catalog right now. Please try again."
    crit, label = METRIC[(out["metric"], out["order"])][lang]
    value = f"{_fmt(out['value'], amps=out['unit'] == 'A')} {out['unit']}"
    pns = out["part_numbers"]
    es_ = lang == "es"
    where = (f"; filtro: {flt}" if es_ else f"; filter: {flt}") if flt else ""
    if out["ties"] == 1:
        if lang == "es":
            return f"Criterio: {crit}{where}, solo modelos disponibles. El {pns[0]} tiene {label}: {value}."
        return f"Criterion: {crit}{where}, available models only. The {pns[0]} has {label}: {value}."
    shown = len(pns)
    if lang == "es":
        extra = f"; muestro {shown}" if out["ties"] > shown else ""
        return f"Criterio: {crit}{where}, solo modelos disponibles. Hay {out['ties']} modelos empatados con {label}: {value}{extra}."
    extra = f"; showing {shown}" if out["ties"] > shown else ""
    return f"Criterion: {crit}{where}, available models only. {out['ties']} models tie with {label}: {value}{extra}."


def _count_desc(filters: Dict[str, Any], lang: str) -> str:
    return _filters_text(filters, lang)


def render_overview(out: Dict[str, Any], lang: str) -> str:
    es = lang == "es"
    status = out.get("status")
    if status == "CATALOG_NOT_FOUND":
        return ("Para comparar necesito dos tamaños de la serie (por ejemplo 761 y 762)." if es
                else "To compare I need two sizes of the series (for example 761 and 762).")
    if status != "CATALOG_OVERVIEW":
        return "No pude consultar el catálogo ahora mismo. Inténtalo de nuevo." if es else "I couldn't query the catalog right now. Please try again."
    aspect = out["aspect"]
    if aspect == "summary":
        volts = _join([f"{v} V" for v in out["voltages"]], lang)
        encs = _join(out["enclosures"], lang)
        if es:
            return (f"El catálogo de la Serie 76 tiene {out['models']} modelos, {out['available']} disponibles y {out['not_available']} listados como N/A, "
                    f"en {out['frame_sizes']} tamaños, con alimentación de {volts} y carcasa {encs}.")
        return (f"The Series 76 catalog has {out['models']} models, {out['available']} available and {out['not_available']} listed as N/A, "
                f"in {out['frame_sizes']} frame sizes, powered at {volts} with {encs} enclosures.")
    if aspect == "count":
        desc = _count_desc(out.get("filters") or {}, lang)
        n, av = out["models"], out["available"]
        if n == 0:
            vs = out.get("voltages_available") or []
            if vs and (out.get("filters") or {}).get("voltage_num") is not None:
                v0 = out["filters"]["voltage_num"]
                items = []
                for x in vs:
                    encs = [_short(ENCLOSURE.get(e, {}).get(lang, e)) for e in x["enclosures"]]
                    only = (f" (solo {encs[0]})" if es else f" ({encs[0]} only)") if len(encs) == 1 else ""
                    items.append(f"{x['voltage']} V{only}")
                return (f"No existe ningún modelo de {v0} V en la Serie 76. Los voltajes que sí se ofrecen son {_join(items, lang)}." if es
                        else f"There is no {v0} V model in the Series 76. The voltages that are offered are {_join(items, lang)}.")
            return (f"No hay modelos {desc} en el catálogo." if es else f"There are no {desc} models in the catalog.")
        what = f" {desc}" if desc else ""
        by_enc: Dict[str, Dict[str, Any]] = {}
        for g in out.get("groups") or []:
            if g["available"]:
                e = by_enc.setdefault(g["enclosure"], {"av": 0, "suf": []})
                e["av"] += g["available"]
                e["suf"].append(g["suffix"])
        tail = ""
        if desc and by_enc:
            enc_txt = [f"{_short(ENCLOSURE.get(e, {}).get(lang, e))}: {v['av']} ({'sufijos' if es else 'suffixes'} {', '.join(v['suf'])})" for e, v in by_enc.items()]
            if len(by_enc) == 1:
                e0 = next(iter(by_enc))
                tail = (f" Solo se ofrecen en carcasa {_short(ENCLOSURE.get(e0, {}).get(lang, e0))} ({'sufijos' if es else 'suffixes'} {', '.join(by_enc[e0]['suf'])})." if es
                        else f" They are only offered in {_short(ENCLOSURE.get(e0, {}).get(lang, e0))} enclosures (suffixes {', '.join(by_enc[e0]['suf'])}).")
            else:
                tail = (" Por carcasa: " if es else " By enclosure: ") + "; ".join(enc_txt) + "."
        if es:
            return (f"Sí. Hay {n} modelos{what} en el catálogo, {av} disponibles." + tail) if desc else f"Hay {n} modelos en el catálogo, {av} disponibles."
        return (f"Yes. There are {n}{what} models in the catalog, {av} available." + tail) if desc else f"There are {n} models in the catalog, {av} available."
    if aspect == "voltages":
        items = [f"{v['value']} V ({v['models']})" for v in out["values"]]
        return (f"Los modelos disponibles se ofrecen en {_join(items, lang)} (entre paréntesis, nº de modelos)." if es
                else f"Available models come in {_join(items, lang)} (model count in brackets).")
    if aspect == "phases":
        items = [f"{PHASE.get(v['value'], {}).get(lang, v['value'])} ({v['models']})" for v in out["values"]]
        return (f"Por tipo de alimentación hay modelos {_join(items, lang)} (nº de modelos disponibles entre paréntesis)." if es
                else f"By supply type there are {_join(items, lang)} models (available count in brackets).")
    if aspect == "enclosures":
        items = [f"{ENCLOSURE.get(v['value'], {}).get(lang, v['value'])} ({v['models']})" for v in out["values"]]
        return (f"Hay carcasas {_join(items, lang)} (nº de modelos disponibles entre paréntesis)." if es
                else f"Enclosures: {_join(items, lang)} (available model count in brackets).")
    if aspect == "sizes":
        items = [f"{s['size']} ({_fmt(s['torque_min_nm'])}–{_fmt(s['torque_max_nm'])} Nm)" for s in out["sizes"]]
        return (f"Hay {len(items)} tamaños: {_join(items, lang)}." if es else f"There are {len(items)} sizes: {_join(items, lang)}.")
    if aspect == "compare_sizes":
        parts: List[str] = []
        for s in out["sizes"]:
            pw = (f"{_fmt(s['power_min_w'])} W" if s["power_min_w"] == s["power_max_w"] else f"{_fmt(s['power_min_w'])}–{_fmt(s['power_max_w'])} W") \
                if s.get("power_min_w") is not None else ("sin dato" if es else "n/a")
            if es:
                parts.append(f"el {s['size']} tiene {s['available']} modelos disponibles de {_fmt(s['torque_min_nm'])} a {_fmt(s['torque_max_nm'])} Nm y motor de {pw}")
            else:
                parts.append(f"the {s['size']} has {s['available']} available models from {_fmt(s['torque_min_nm'])} to {_fmt(s['torque_max_nm'])} Nm and a {pw} motor")
        text = "; ".join(parts) + "."
        return text[0].upper() + text[1:]
    return ""
