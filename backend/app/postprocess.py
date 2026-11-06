"""Postprocesado determinista de la respuesta del LLM: texto plano y corto (la app muestra la ficha completa).

clean_text(): quita **negritas**, _cursivas_, `codigo`, #encabezados, tablas y vinas/listas, y colapsa saltos de linea.
shorten(): cuando hay tarjetas, deja como maximo MAX_SENTENCES frases / MAX_WORDS palabras (solo recorta, nunca anade).
"""
import re
from typing import List

MAX_SENTENCES = 2
MAX_WORDS = 45

_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡0-9(])")


def _table_row_to_text(line: str) -> str:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return ", ".join(c for c in cells if c)


def clean_text(text: str) -> str:
    if not text:
        return ""
    out: List[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if _TABLE_SEP.match(line) and "-" in line:
            continue
        if line.count("|") >= 2:
            line = _table_row_to_text(line)
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)           # encabezados
        line = re.sub(r"^\s*(?:[-*•·▪‣]|\d{1,2}[.)])\s+", "", line)  # viñetas y listas numeradas
        line = re.sub(r"^\s*>\s?", "", line)                     # citas
        line = re.sub(r"(\*\*|__)(.+?)\1", r"\2", line)          # negritas
        line = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]+?)\*(?![\w*])", r"\1", line)  # cursivas *x*
        line = re.sub(r"`([^`]*)`", r"\1", line)                 # código en línea
        line = line.replace("**", "").replace("__", "")
        if line.strip():
            out.append(line.strip())
    cleaned = " ".join(out)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def shorten(text: str, max_sentences: int = MAX_SENTENCES, max_words: int = MAX_WORDS) -> str:
    if not text:
        return text
    sentences = _SENTENCE_SPLIT.split(text.strip())
    kept = sentences[:max_sentences]
    result = " ".join(kept)
    words = result.split()
    if len(words) > max_words:
        # se corta en la ultima frase completa que cabe; si ni la primera cabe, se deja la primera entera
        acc: List[str] = []
        for s in kept:
            if len((" ".join(acc + [s])).split()) <= max_words:
                acc.append(s)
            else:
                break
        result = " ".join(acc) if acc else kept[0]
    return result
