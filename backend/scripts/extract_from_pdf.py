"""Extracción VLM del catálogo desde el PDF (solo imagen) + reconciliación A/B.

Pase A: gemini en OpenRouter, recortes por tabla a 300 dpi.
Pase B: pase independiente (NIM si hay clave nvapi, si no gemini con recortes a 400 dpi y otro margen).
Salida cruda en backend/data/extraction/{A,B}.json; reconciliación en reconciliation.json.
"""
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass

import base64
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pypdfium2 as pdfium
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, ValidationError

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
PDF_PATH = ROOT / "docs" / "series_76_electric_data.pdf"
EXTRACTION_DIR = ROOT / "backend" / "data" / "extraction"
CROPS_DIR = EXTRACTION_DIR / "crops"
DRAFT_PATH = ROOT / "backend" / "data" / "reference" / "ref_draft.json"

PREVIEW_W, PREVIEW_H = 1236.0, 1600.0  # geometría (px) usada para medir las cajas de abajo


class Tbl:
    def __init__(self, key, page, kind, enclosure, supply, volt, phase, box, header_h, first_y, last_y, n):
        self.key, self.page, self.kind = key, page, kind
        self.enclosure, self.supply, self.volt, self.phase = enclosure, supply, volt, phase
        self.box, self.header_h, self.first_y, self.last_y, self.n = box, header_h, first_y, last_y, n


# box = (x0, y0, x1, y1) en px de preview; first_y/last_y = centros de la primera/última fila
TABLES = [
    Tbl("p1_110v", 1, "ac", "Weatherproof", "110V Single Phase", 110, "Single Phase", (150, 283, 1050, 668), 395, 413, 649, 11),
    Tbl("p1_220v", 1, "ac", "Weatherproof", "220V Single Phase", 220, "Single Phase", (150, 678, 1050, 1200), 790, 808, 1162, 16),
    Tbl("p2_3ph", 2, "3ph", "Weatherproof", "220V 3 Phase", 220, "3 Phase", (150, 298, 1060, 628), 392, 404, 611, 11),
    Tbl("p3_24v_onoff", 3, "24v_onoff", "Explosionproof", "24V AC/DC On/Off", 24, "DC", (160, 263, 1030, 475), 355, 368, 459, 5),
    Tbl("p3_24v_mod", 3, "24v_mod", "Explosionproof", "24V DC Modulating", 24, "DC", (160, 483, 1030, 697), 575, 588, 680, 5),
    Tbl("p4_110v", 4, "ac", "Explosionproof", "110V Single Phase", 110, "Single Phase", (150, 270, 1045, 632), 390, 402, 616, 10),
    Tbl("p4_220v", 4, "ac", "Explosionproof", "220V Single Phase", 220, "Single Phase", (150, 643, 1045, 1006), 762, 775, 988, 10),
]


# ---------------------------------------------------------------- esquemas Pydantic
class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_part_number: str


class ACRow(_Row):
    on_off_torque_in_lbs: float
    on_off_torque_nm: float
    on_off_duty_cycle_pct: int
    cycles_per_hour: int
    modulating_torque_in_lbs: float
    modulating_torque_nm: float
    modulating_duty_cycle_pct: int
    starts_per_hour: int
    speed_60hz_sec: float
    speed_50hz_sec: float
    fla_60hz_amps: float
    fla_50hz_amps: float
    lra_60hz_amps: float
    lra_50hz_amps: float
    motor_power_watts: int


class ThreePhaseRow(_Row):
    is_available: bool
    # La tabla trifásica tiene UN solo torque/duty/cycles/starts; se guarda en las columnas on_off_*.
    on_off_torque_in_lbs: Optional[float] = None
    on_off_torque_nm: Optional[float] = None
    on_off_duty_cycle_pct: Optional[int] = None
    cycles_per_hour: Optional[int] = None
    starts_per_hour: Optional[int] = None
    speed_60hz_sec: Optional[float] = None
    speed_50hz_sec: Optional[float] = None
    fla_60hz_amps: Optional[float] = None
    fla_50hz_amps: Optional[float] = None
    lra_60hz_amps: Optional[float] = None
    lra_50hz_amps: Optional[float] = None
    motor_power_watts: Optional[int] = None


class OnOff24Row(_Row):
    on_off_torque_in_lbs: float
    on_off_torque_nm: float
    on_off_duty_cycle_pct: int
    cycles_per_hour: int
    speed_dc_or_fixed_sec: float
    fla_dc_or_fixed_amps: float
    lra_dc_or_fixed_amps: float
    motor_power_watts: int


class Mod24Row(_Row):
    modulating_torque_in_lbs: float
    modulating_torque_nm: float
    modulating_duty_cycle_pct: int
    starts_per_hour: int
    speed_dc_or_fixed_sec: float
    fla_dc_or_fixed_amps: float
    lra_dc_or_fixed_amps: float
    motor_power_watts: int


KIND_MODEL = {"ac": ACRow, "3ph": ThreePhaseRow, "24v_onoff": OnOff24Row, "24v_mod": Mod24Row}

COMMON_RULES = """You are transcribing ONE table from a scanned industrial datasheet image. Output ONLY a JSON object {"rows": [...]}.
Rules:
- One JSON object per table row, in visual order, top to bottom. Do not skip, merge or invent rows.
- base_part_number: copy it character by character exactly as printed (e.g. digits vs letters B/8, O/0/C matter). Do not include a trailing '*' footnote mark and do not 'correct' it.
- Numbers: plain JSON numbers, no thousands separators ('1,330' -> 1330), keep decimals as printed ('2.0' -> 2.0).
- Motor Power (Watts) cells are vertically merged across several rows: repeat that value in EVERY row the merged cell spans.
- Never estimate, compute or fix values; transcribe what is printed.
"""

KIND_PROMPT = {
    "ac": COMMON_RULES + """Table columns, left to right: Base Part Number | On/Off torque In-Lbs, Nm | On/Off duty cycle S4% | Cycles per hour | Modulating torque In-Lbs, Nm | Modulating duty cycle S4% | Starts per hour | Operating speed (sec) 60 Hz, 50 Hz | FLA 60 Hz, 50 Hz | LRA 60 Hz, 50 Hz | Motor power Watts.
The sub-column order is ALWAYS 60 Hz (left) then 50 Hz (right) for speed, FLA and LRA; read the printed header to confirm, and map left->*_60hz_*, right->*_50hz_*.
Row keys: base_part_number, on_off_torque_in_lbs, on_off_torque_nm, on_off_duty_cycle_pct, cycles_per_hour, modulating_torque_in_lbs, modulating_torque_nm, modulating_duty_cycle_pct, starts_per_hour, speed_60hz_sec, speed_50hz_sec, fla_60hz_amps, fla_50hz_amps, lra_60hz_amps, lra_50hz_amps, motor_power_watts.""",
    "3ph": COMMON_RULES + """Table columns: Base Part Number | Output torque In-Lbs, Nm | Duty cycle S4% | Cycles per hour | Starts per hour | Operating speed (sec) 60 Hz, 50 Hz | FLA 60 Hz, 50 Hz | LRA 60 Hz, 50 Hz | Motor power Watts.
Read the printed header of each sub-column pair and map by its label: the left/right order is whatever the header prints; assign by label (60 Hz -> *_60hz_*, 50 Hz -> *_50hz_*).
Some rows are marked N/A across all metrics: for those rows output is_available=false and null for every other field. Other rows: is_available=true.
Row keys: base_part_number, is_available, on_off_torque_in_lbs (In-Lbs of the single Output Torque), on_off_torque_nm, on_off_duty_cycle_pct, cycles_per_hour, starts_per_hour, speed_60hz_sec, speed_50hz_sec, fla_60hz_amps, fla_50hz_amps, lra_60hz_amps, lra_50hz_amps, motor_power_watts.""",
    "24v_onoff": COMMON_RULES + """This 24V table has NO 50/60 Hz sub-columns. Columns: Base Part Number | On/Off torque In-Lbs, Nm | On/Off duty cycle S4% | Cycles per hour | Operating speed Sec | FLA Amps | LRA Amps | Motor power Watts.
Row keys: base_part_number, on_off_torque_in_lbs, on_off_torque_nm, on_off_duty_cycle_pct, cycles_per_hour, speed_dc_or_fixed_sec, fla_dc_or_fixed_amps, lra_dc_or_fixed_amps, motor_power_watts.""",
    "24v_mod": COMMON_RULES + """This 24V table has NO 50/60 Hz sub-columns. Columns: Base Part Number | Modulating torque In-Lbs, Nm | Modulating duty cycle S4% | Starts per hour | Operating speed Sec | FLA Amps | LRA Amps | Motor power Watts.
Row keys: base_part_number, modulating_torque_in_lbs, modulating_torque_nm, modulating_duty_cycle_pct, starts_per_hour, speed_dc_or_fixed_sec, fla_dc_or_fixed_amps, lra_dc_or_fixed_amps, motor_power_watts.""",
}


# ---------------------------------------------------------------- imágenes
def pdf_sha256() -> str:
    return hashlib.sha256(PDF_PATH.read_bytes()).hexdigest()


def render_page(page_no: int, dpi: int):
    doc = pdfium.PdfDocument(str(PDF_PATH))
    return doc[page_no - 1].render(scale=dpi / 72).to_pil().convert("RGB")


def crop_table(img, t: Tbl, pad: int):
    w, h = img.size
    sx, sy = w / PREVIEW_W, h / PREVIEW_H
    x0, y0, x1, y1 = t.box
    return img.crop((max(0, int((x0 - pad) * sx)), max(0, int((y0 - pad) * sy)), min(w, int((x1 + pad) * sx)), min(h, int((y1 + pad) * sy))))


def png_b64(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------- llamadas VLM
class VLM:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model
        self.cost = 0.0

    def call(self, prompt: str, img) -> str:
        body = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 8000,
            "chat_template_kwargs": {"enable_thinking": False},  # nemotron-vl razona hasta agotar max_tokens si no se apaga
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt + " Return raw JSON only, no commentary."},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + png_b64(img)}},
            ]}],
        }
        for wait in (5, 15, 30, 60, 0):
            r = httpx.post(f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, json=body, timeout=150)
            if r.status_code not in (429, 500, 502, 503, 504) or not wait:
                break
            time.sleep(wait)  # errores transitorios de admisión/créditos de OpenRouter
        if r.status_code >= 400:
            raise RuntimeError(f"{r.status_code} {r.text[:300]}")
        j = r.json()
        self.cost += float((j.get("usage") or {}).get("cost") or 0)
        return j["choices"][0]["message"]["content"] or ""


def parse_json(text: str) -> Dict[str, Any]:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)


def extract_table(vlm: VLM, t: Tbl, img) -> List[Dict[str, Any]]:
    model_cls = KIND_MODEL[t.kind]
    last_err = None
    for attempt in range(3):
        try:
            data = parse_json(vlm.call(KIND_PROMPT[t.kind], img))
            rows = [model_cls.model_validate(r).model_dump() for r in data["rows"]]
            if len(rows) != t.n:
                raise ValueError(f"{len(rows)} filas, se esperaban {t.n}")
            return rows
        except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as e:
            last_err = e; print(f"    intento {attempt+1} falló: {str(e)[:120]}", flush=True)
    raise RuntimeError(f"{t.key}: extracción inválida tras 3 intentos: {last_err}")


def run_pass(label: str, vlm: VLM, dpi: int, pad: int) -> Dict[str, Any]:
    out = {"pass": label, "model": vlm.model, "provider": vlm.base_url, "dpi": dpi, "pad_px": pad,
           "date": datetime.now(timezone.utc).isoformat(), "pdf_sha256": pdf_sha256(), "tables": {}}
    pages: Dict[int, Any] = {}
    for t in TABLES:
        if t.page not in pages:
            pages[t.page] = render_page(t.page, dpi)
        rows = extract_table(vlm, t, crop_table(pages[t.page], t, pad))
        out["tables"][t.key] = {"page": t.page, "kind": t.kind, "rows": rows}
        print(f"  [{label}] {t.key}: {len(rows)} filas")
    out["cost_usd"] = round(vlm.cost, 5)
    return out


# ---------------------------------------------------------------- reconciliación
def flat(extraction: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    res = {}
    for tk, tb in extraction["tables"].items():
        for r in tb["rows"]:
            pn = r["base_part_number"].strip()
            res[pn] = {"_table": tk, "_page": tb["page"], **{k: v for k, v in r.items() if k != "base_part_number"}}
    return res


def reconcile(A: Dict[str, Any]) -> Dict[str, Any]:
    """Pase A (VLM) vs pase B (borrador manual independiente), campo a campo.

    Las filas se emparejan por posición dentro de cada tabla (el borrador conserva el orden del PDF),
    de modo que un número de parte mal leído es UN desacuerdo del campo base_part_number y no dos filas huérfanas.
    """
    draft = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))["rows"]
    dkeys = list(draft)
    agree = differ = 0
    accepted: Dict[str, Dict[str, Any]] = {}
    review: List[Dict[str, Any]] = []
    # Emparejamiento 1:1 fila A <-> clave del borrador: exacto primero, luego por similitud del número de parte.
    import difflib

    a_all = [(t, idx, r["base_part_number"].strip()) for t in TABLES for idx, r in enumerate(A["tables"][t.key]["rows"])]
    pair: Dict[tuple, Optional[str]] = {}
    free = set(dkeys)
    for t, idx, apn in a_all:
        if apn in free:
            pair[(t.key, idx)] = apn
            free.discard(apn)
    leftovers = [(t, idx, apn) for t, idx, apn in a_all if (t.key, idx) not in pair]
    scored = sorted(((difflib.SequenceMatcher(None, apn, k).ratio(), t.key, idx, k) for t, idx, apn in leftovers for k in free), reverse=True)
    for sc, tk, idx, k in scored:
        if (tk, idx) not in pair and k in free:
            pair[(tk, idx)] = k
            free.discard(k)
    for t in TABLES:
        a_rows = A["tables"][t.key]["rows"]
        for idx, ra in enumerate(a_rows):
            dpn = pair.get((t.key, idx))
            apn = ra["base_part_number"].strip()
            d = draft.get(dpn) if dpn else None
            rb = {"is_available": False} if d == "N/A" else {**(d or {}), "is_available": True}
            ra = {**ra, "is_available": ra.get("is_available", True)}  # solo la tabla trifásica emite N/A
            base = {"page": t.page, "table": t.key, "row_index": idx}
            if apn == dpn:
                agree += 1
            else:
                differ += 1
                review.append({**base, "part_number": apn, "field": "base_part_number", "A": apn, "B_draft": dpn})
            rec = {"_table": t.key, "_page": t.page, "base_part_number": apn if apn == dpn else None}
            for f in sorted((set(ra) | set(rb)) - {"base_part_number"}):
                va, vb = ra.get(f), rb.get(f)
                if va == vb:
                    agree += 1
                    rec[f] = va
                else:
                    differ += 1
                    review.append({**base, "part_number": apn, "field": f, "A": va, "B_draft": vb})
            accepted[dpn or apn] = rec
    return {"generated": datetime.now(timezone.utc).isoformat(), "pdf_sha256": A["pdf_sha256"],
            "sources": {"A": "nvidia/nemotron-3.5-super-vl-120b-a12b (NIM; p1_110v con llama-3.2-90b-vision)", "B": "backend/data/reference/ref_draft.json (manual)"},
            "n_rows_A": sum(len(t["rows"]) for t in A["tables"].values()), "n_rows_B": len(dkeys),
            "fields_agree": agree, "fields_differ": differ, "needs_review": review, "accepted": accepted}


# ---------------------------------------------------------------- recortes de verificación
def review_crop(item: Dict[str, Any]) -> Optional[Path]:
    """Recorte del encabezado de la tabla + la fila del desacuerdo (posición estimada por paso uniforme)."""
    from PIL import Image

    t = next((x for x in TABLES if x.key == item.get("table")), None)
    if t is None:
        return None
    idx = item["row_index"]
    pitch = (t.last_y - t.first_y) / max(1, t.n - 1)
    cy = t.first_y + idx * pitch
    img = render_page(t.page, 300)
    w, h = img.size
    sx, sy = w / PREVIEW_W, h / PREVIEW_H
    x0, _, x1, _ = t.box
    head = img.crop((int((x0 - 5) * sx), int((t.box[1]) * sy), int((x1 + 5) * sx), int((t.header_h) * sy)))
    row = img.crop((int((x0 - 5) * sx), int((cy - 1.4 * pitch) * sy), int((x1 + 5) * sx), int((cy + 1.4 * pitch) * sy)))
    canvas = Image.new("RGB", (head.width, head.height + row.height + 6), "white")
    canvas.paste(head, (0, 0))
    canvas.paste(row, (0, head.height + 6))
    p = CROPS_DIR / f"p{item['page']}_{item['table']}_row{idx + 1:02d}.png"
    canvas.save(p)
    return p


A_CACHE: Dict[str, Any] = {}


NIM_BASE = "https://integrate.api.nvidia.com/v1"
NIM_MODELS = ["nvidia/nemotron-3.5-super-vl-120b-a12b", "meta/llama-3.2-90b-vision-instruct", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"]


def run_pass_nim(key: str, dpi: int = 300, pad: int = 10) -> Dict[str, Any]:
    out = {"pass": "A", "provider": NIM_BASE, "dpi": dpi, "pad_px": pad, "date": datetime.now(timezone.utc).isoformat(),
           "pdf_sha256": pdf_sha256(), "model": NIM_MODELS[0], "table_models": {}, "tables": {}}
    pages: Dict[int, Any] = {}
    partial = EXTRACTION_DIR / "A.partial.json"
    done = json.loads(partial.read_text(encoding="utf-8")) if partial.exists() else {}
    for t in TABLES:
        if t.key in done:
            out["tables"][t.key] = done[t.key]
            out["table_models"][t.key] = done[t.key]["model"]
            print(f"  [A] {t.key}: reutilizada ({done[t.key]['model']})")
            continue
        pages.setdefault(t.page, render_page(t.page, dpi))
        img = crop_table(pages[t.page], t, pad)
        for m in NIM_MODELS:
            try:
                rows = extract_table(VLM(NIM_BASE, key, m), t, img)
                out["table_models"][t.key] = m
                break
            except Exception as e:  # noqa: BLE001
                print(f"  [A] {t.key}: {m} falló ({str(e)[:160]})")
        else:
            raise SystemExit(f"{t.key}: todos los modelos NIM fallaron")
        out["tables"][t.key] = {"page": t.page, "kind": t.kind, "model": out["table_models"][t.key], "rows": rows}
        done[t.key] = out["tables"][t.key]
        partial.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
        print(f"  [A] {t.key}: {len(rows)} filas con {out['table_models'][t.key]}")
    return out


def main() -> None:
    key = os.environ["LLM_API_KEY_NIM"]
    EXTRACTION_DIR.mkdir(parents=True, exist_ok=True)
    CROPS_DIR.mkdir(parents=True, exist_ok=True)
    A = run_pass_nim(key)
    (EXTRACTION_DIR / "A.json").write_text(json.dumps(A, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.copy(DRAFT_PATH, EXTRACTION_DIR / "B.json")  # pase B = borrador manual independiente
    rec = reconcile(A)
    A_CACHE.update(A)
    for item in rec["needs_review"]:
        p = review_crop(item)
        item["crop"] = str(p.relative_to(ROOT)).replace("\\", "/") if p else None
    (EXTRACTION_DIR / "reconciliation.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"filas A={rec['n_rows_A']} B={rec['n_rows_B']} | campos A=B: {rec['fields_agree']} | difieren: {rec['fields_differ']}")


if __name__ == "__main__":
    sys.exit(main())
