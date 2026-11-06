"""Construye backend/data/series76_catalog.json (+ backend/evals/oracle/golden.json) desde la extracción reconciliada.

Valor final = valor acordado A=B; en desacuerdos solo se aplican resoluciones humanas explícitas
(backend/data/extraction/human_resolutions.json). Cualquier desacuerdo sin resolución aborta.
Los metadatos estructurales (envolvente, tensión, fase, certificaciones) salen de la definición de tabla, no del VLM.
"""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
EXTRACTION_DIR = ROOT / "backend" / "data" / "extraction"
CATALOG_PATH = ROOT / "backend" / "data" / "series76_catalog.json"
GOLDEN_PATH = ROOT / "backend" / "evals" / "oracle" / "golden.json"

HAZ_CERT = "Class I, Division 1, Groups C, D, T4 | Ex d IIB T4 Gb | Class I, Zone 1, AEx d IIB T4 Gb"
COMMON_NOTES = [
    "1. Full load current (FLA) = Max. rated load",
    "2. Locked rotor current (LRA) @ Locked rotor load",
    "3. Allowable motor voltage tolerance: +/-10%",
    "4. Allowable power frequency tolerance: +/-5%",
    "5. Duty cycle per IEC 60034-1 for on/off and modulating service",
    "6. Starts and cycles per hour based on rated torque",
]
NO_CSA_NOTE = "* Sizes 6 and 7 are not CSA Certified"

# table key -> metadatos estructurales
TABLE_META = {
    "p1_110v": dict(enclosure_type="Weatherproof", power_supply="110V Single Phase", voltage_num=110, phase_type="Single Phase", service_support="Both On/Off & Modulating", ce_ukca_certified=True, hazardous=False),
    "p1_220v": dict(enclosure_type="Weatherproof", power_supply="220V Single Phase", voltage_num=220, phase_type="Single Phase", service_support="Both On/Off & Modulating", ce_ukca_certified=True, hazardous=False),
    "p2_3ph": dict(enclosure_type="Weatherproof", power_supply="220V 3 Phase", voltage_num=220, phase_type="3 Phase", service_support="Both On/Off & Modulating", ce_ukca_certified=True, hazardous=False),
    "p3_24v_onoff": dict(enclosure_type="Explosionproof", power_supply="24V AC/DC", voltage_num=24, phase_type="AC/DC", service_support="On/Off Only", ce_ukca_certified=False, hazardous=True),
    "p3_24v_mod": dict(enclosure_type="Explosionproof", power_supply="24V DC", voltage_num=24, phase_type="DC", service_support="Modulating Only", ce_ukca_certified=False, hazardous=True),
    "p4_110v": dict(enclosure_type="Explosionproof", power_supply="110V Single Phase", voltage_num=110, phase_type="Single Phase", service_support="Both On/Off & Modulating", ce_ukca_certified=False, hazardous=True),
    "p4_220v": dict(enclosure_type="Explosionproof", power_supply="220V Single Phase", voltage_num=220, phase_type="Single Phase", service_support="Both On/Off & Modulating", ce_ukca_certified=False, hazardous=True),
}

FIELDS = [
    "on_off_torque_in_lbs", "on_off_torque_nm", "on_off_duty_cycle_pct", "cycles_per_hour",
    "modulating_torque_in_lbs", "modulating_torque_nm", "modulating_duty_cycle_pct", "starts_per_hour",
    "speed_60hz_sec", "speed_50hz_sec", "speed_dc_or_fixed_sec",
    "fla_60hz_amps", "fla_50hz_amps", "fla_dc_or_fixed_amps",
    "lra_60hz_amps", "lra_50hz_amps", "lra_dc_or_fixed_amps", "motor_power_watts",
]


def build_catalog(reconciliation: Dict[str, Any], extraction_a: Dict[str, Any]) -> List[Dict[str, Any]]:
    res = json.loads((EXTRACTION_DIR / "human_resolutions.json").read_text(encoding="utf-8"))
    human = {(r["part_number"], r["field"]): r for r in res["field_values"]}
    by_row: Dict[tuple, List[Dict[str, Any]]] = {}
    for d in reconciliation["needs_review"]:
        by_row.setdefault((d["table"], d["row_index"]), []).append(d)

    records: List[Dict[str, Any]] = []
    for tkey, tb in extraction_a["tables"].items():
        meta = TABLE_META[tkey]
        for idx, row in enumerate(tb["rows"]):
            diffs = by_row.get((tkey, idx), [])
            final = {k: v for k, v in row.items() if k != "base_part_number"}
            final.setdefault("is_available", True)
            pn_a = row["base_part_number"].strip()
            pn = pn_a
            prov_fields = []
            for d in sorted(diffs, key=lambda x: x["field"] != "base_part_number"):  # primero el número de parte
                f = d["field"]
                if f == "base_part_number":
                    cand = d["B_draft"]
                    if pn_a.rstrip("*") != cand and not _extra_zero(pn_a, cand):
                        raise SystemExit(f"Desacuerdo de número de parte sin regla humana: {pn_a} vs {cand}")
                    pn = cand
                    prov_fields.append({"field": f, "A": d["A"], "B": d["B_draft"], "final": pn, "resolved_by": "human_rule"})
                else:
                    h = human.get((pn, f))
                    if h is None:
                        raise SystemExit(f"Desacuerdo sin resolución humana: {pn_a} {f} A={d['A']} B={d['B_draft']}")
                    final[f] = h["value"]
                    prov_fields.append({"field": f, "A": d["A"], "B": d["B_draft"], "final": h["value"], "resolved_by": "human"})
            frame = int(pn[2])
            no_csa = meta["enclosure_type"] == "Weatherproof" and meta["power_supply"] == "220V Single Phase" and frame in (6, 7)
            available = bool(final.pop("is_available"))
            rec: Dict[str, Any] = {
                "base_part_number": pn, "size_code": pn[:4], "frame_size": frame,
                "enclosure_type": meta["enclosure_type"], "power_supply": meta["power_supply"],
                "voltage_num": meta["voltage_num"], "phase_type": meta["phase_type"],
                "service_support": meta["service_support"] if available else "N/A (Not Available in 220V 3-Phase)",
                "is_available": available,
            }
            for f in FIELDS:
                rec[f] = final.get(f) if available else None
            rec.update({
                "csa_certified": available and not no_csa,
                "ce_ukca_certified": available and meta["ce_ukca_certified"],
                "hazardous_classification": HAZ_CERT if meta["hazardous"] else None,
                "table_notes": ["Model listed as N/A in 220V 3-Phase table."] if not available else COMMON_NOTES + ([NO_CSA_NOTE] if no_csa else []),
                "source_page": tb["page"],
                "provenance": {
                    "page": tb["page"], "table": tkey,
                    "method": "A+B+humano" if diffs else "A=B",
                    "disagreements": prov_fields,
                },
            })
            records.append(rec)
    return records


def _extra_zero(a: str, b: str) -> bool:
    """A tiene un '0' de más respecto al borrador (error de conteo del VLM)."""
    return len(a) == len(b) + 1 and any(a[:i] + a[i + 1:] == b for i in range(len(a)) if a[i] == "0")


def write_catalog(records: List[Dict[str, Any]], pdf_sha256: str) -> None:
    if len(records) != 68 or len({r["base_part_number"] for r in records}) != 68:
        raise SystemExit(f"Se esperaban 68 registros únicos, hay {len(records)}")
    doc = {"_meta": {"generated": datetime.now(timezone.utc).isoformat(), "source": "docs/series_76_electric_data.pdf",
                     "pdf_sha256": pdf_sha256, "n_records": len(records),
                     "method": "A (NIM VLM) + B (borrador manual) reconciliados campo a campo; desacuerdos resueltos por humano"},
           "records": records}
    CATALOG_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(CATALOG_PATH, GOLDEN_PATH)  # golden = copia verificada


def main() -> None:
    rec = json.loads((EXTRACTION_DIR / "reconciliation.json").read_text(encoding="utf-8"))
    a = json.loads((EXTRACTION_DIR / "A.json").read_text(encoding="utf-8"))
    records = build_catalog(rec, a)
    write_catalog(records, a["pdf_sha256"])
    m = sum(r["provenance"]["method"] == "A+B+humano" for r in records)
    print(f"{len(records)} registros escritos; A=B: {len(records) - m}, A+B+humano: {m}")


if __name__ == "__main__":
    main()
