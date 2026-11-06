try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import os
import re
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import psycopg
from psycopg.rows import dict_row
import bcrypt
import pypdfium2 as pdfium
from pydantic import BaseModel, Field, model_validator

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("series76_ingest")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR.parent / "docs" if (BASE_DIR.parent / "docs").exists() else BASE_DIR / "docs"


# =====================================================================
# 1. VALIDADOR FÍSICO Y DE DOMINIO (GUARDRAIL DETERMINISTA DE INGESTA)
# =====================================================================
class ActuatorRecord(BaseModel):
    base_part_number: str
    size_code: str
    frame_size: int
    enclosure_type: str
    power_supply: str
    voltage_num: int
    phase_type: str
    service_support: str
    is_available: bool = True

    on_off_torque_in_lbs: Optional[float] = None
    on_off_torque_nm: Optional[float] = None
    on_off_duty_cycle_pct: Optional[int] = None
    cycles_per_hour: Optional[int] = None

    modulating_torque_in_lbs: Optional[float] = None
    modulating_torque_nm: Optional[float] = None
    modulating_duty_cycle_pct: Optional[int] = None
    starts_per_hour: Optional[int] = None

    speed_60hz_sec: Optional[float] = None
    speed_50hz_sec: Optional[float] = None
    speed_dc_or_fixed_sec: Optional[float] = None

    fla_60hz_amps: Optional[float] = None
    fla_50hz_amps: Optional[float] = None
    fla_dc_or_fixed_amps: Optional[float] = None

    lra_60hz_amps: Optional[float] = None
    lra_50hz_amps: Optional[float] = None
    lra_dc_or_fixed_amps: Optional[float] = None

    motor_power_watts: Optional[int] = None
    csa_certified: bool = True
    ce_ukca_certified: bool = False
    hazardous_classification: Optional[str] = None
    table_notes: List[str] = Field(default_factory=list)
    source_page: int
    source_method: Optional[str] = None  # procedencia de la extracción (provenance.method del catálogo)

    @property
    def normalized_part_number(self) -> str:
        return re.sub(r"[^A-Z0-9]", "", self.base_part_number.upper())

    @model_validator(mode="after")
    def verify_physical_laws(self) -> "ActuatorRecord":
        """Leyes físicas del catálogo. NUNCA corrige en silencio: si algo falla, levanta ValueError y la ingesta aborta."""
        if not self.is_available:
            return self
        pn = self.base_part_number
        errors: List[str] = []

        # 1 Nm ≈ 8.85 in-lbs
        for label, inlbs, nm in [
            ("On/Off", self.on_off_torque_in_lbs, self.on_off_torque_nm),
            ("Modulating", self.modulating_torque_in_lbs, self.modulating_torque_nm),
        ]:
            if inlbs is not None and nm is not None:
                ratio = inlbs / nm
                if not (8.2 <= ratio <= 9.5):
                    errors.append(f"torque {label}: {inlbs} in-lbs / {nm} Nm = {ratio:.2f} fuera de [8.2, 9.5]")

        # LRA >= FLA
        for freq, fla, lra in [
            ("60Hz", self.fla_60hz_amps, self.lra_60hz_amps),
            ("50Hz", self.fla_50hz_amps, self.lra_50hz_amps),
            ("DC/Fixed", self.fla_dc_or_fixed_amps, self.lra_dc_or_fixed_amps),
        ]:
            if fla is not None and lra is not None and lra < fla:
                errors.append(f"LRA < FLA @ {freq}: LRA={lra}A FLA={fla}A")

        # velocidad 60 Hz < velocidad 50 Hz (a 60 Hz el motor gira más rápido, el recorrido tarda menos)
        if self.speed_60hz_sec is not None and self.speed_50hz_sec is not None:
            if not self.speed_60hz_sec < self.speed_50hz_sec:
                errors.append(f"velocidad 60Hz ({self.speed_60hz_sec}s) no es < velocidad 50Hz ({self.speed_50hz_sec}s)")

        # torque on/off >= torque modulante
        if self.on_off_torque_nm is not None and self.modulating_torque_nm is not None:
            if self.on_off_torque_nm < self.modulating_torque_nm:
                errors.append(f"torque on/off ({self.on_off_torque_nm} Nm) < torque modulante ({self.modulating_torque_nm} Nm)")

        # CSA: solo tamaños 6 y 7 en 220V monofásico weatherproof (766A-767C) no están certificados
        expect_no_csa = (
            self.enclosure_type == "Weatherproof" and self.power_supply == "220V Single Phase" and self.frame_size in (6, 7)
        )
        if expect_no_csa and self.csa_certified:
            errors.append("tamaño 6/7 en 220V monofásico weatherproof debe tener csa_certified=false")
        if not expect_no_csa and not self.csa_certified:
            errors.append("csa_certified=false fuera de 766A-767C 220V monofásico weatherproof")

        if errors:
            raise ValueError(f"{pn}: " + "; ".join(errors))
        return self


# =====================================================================
# 2. CATÁLOGO: SOLO LECTURA DE backend/data/series76_catalog.json
# =====================================================================
CATALOG_PATH = DATA_DIR / "series76_catalog.json"


def load_catalog(path: Path = CATALOG_PATH) -> List[ActuatorRecord]:
    """Carga y valida los 68 registros. Si alguna fila viola una ley física, falla y las lista todas."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    records: List[ActuatorRecord] = []
    failures: List[str] = []
    for raw in doc["records"]:
        prov = raw.get("provenance") or {}
        raw = {k: v for k, v in raw.items() if k != "provenance"}
        raw["source_method"] = prov.get("method")
        try:
            records.append(ActuatorRecord(**raw))
        except Exception as e:  # noqa: BLE001
            failures.append(" | ".join(str(e).splitlines()))
    if failures:
        raise SystemExit("Ingesta ABORTADA, filas inválidas:\n  - " + "\n  - ".join(failures))
    if len(records) != 68:
        raise SystemExit(f"Se esperaban 68 registros, hay {len(records)}")
    logger.info(f"✅ {len(records)} registros validados desde {path.name}")
    return records


def run_from_pdf() -> None:
    """Re-ejecuta la extracción (NIM VLM), reconcilia con el borrador, aplica resoluciones humanas y reescribe el catálogo."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import extract_from_pdf as ex
    import build_catalog as bc

    ex.main()
    rec = json.loads((ex.EXTRACTION_DIR / "reconciliation.json").read_text(encoding="utf-8"))
    a = json.loads((ex.EXTRACTION_DIR / "A.json").read_text(encoding="utf-8"))
    bc.write_catalog(bc.build_catalog(rec, a), a["pdf_sha256"])


# =====================================================================
# 4. PERSISTENCIA EN ARCHIVOS JSON Y CARGA EN POSTGRESQL
# =====================================================================
def save_snapshots(records: List[ActuatorRecord]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    actuators_path = DATA_DIR / "processed_actuators.json"

    with open(actuators_path, "w", encoding="utf-8") as f:
        json.dump([r.model_dump() for r in records], f, indent=2, ensure_ascii=False)

    logger.info(f"💾 Snapshot guardado en {actuators_path}")


def resolve_db_url() -> str:
    """En contenedor usa host `db`; desde el host apunta a localhost:DB_HOST_PORT."""
    url = os.getenv("DATABASE_URL", "postgresql://konecto:konecto_secret_2026@db:5432/series76_db")
    url = url.replace("postgresql+psycopg://", "postgresql://")
    if not Path("/.dockerenv").exists():
        url = re.sub(r"@db:\d+", "@localhost:" + os.getenv("DB_HOST_PORT", "5433"), url)
    return url


def seed_database(records: List[ActuatorRecord]) -> None:
    db_url = resolve_db_url()

    with psycopg.connect(db_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            # 1. Crear usuarios de prueba para el Feature Opcional de Login
            test_users = [
                ("engineer@konecto.io", os.getenv("DEMO_PASSWORD_ENGINEER", "Konecto2026!"), "Lead Plant Engineer", "plant_engineer"),
                ("supervisor@konecto.io", os.getenv("DEMO_PASSWORD_SUPERVISOR", "Series76Pass!"), "Automation Supervisor", "supervisor"),
                ("admin@konecto.io", os.getenv("DEMO_PASSWORD_ADMIN", "AdminKonecto!"), "System Evaluator", "admin"),
            ]
            for email, raw_pwd, name, role in test_users:
                pwd_hash = bcrypt.hashpw(raw_pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                cur.execute(
                    """
                    INSERT INTO users (email, password_hash, full_name, role)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (email) DO UPDATE
                    SET password_hash = EXCLUDED.password_hash, full_name = EXCLUDED.full_name;
                    """,
                    (email, pwd_hash, name, role),
                )

            # 2. Limpiar y recargar catálogo de actuadores
            cur.execute("ALTER TABLE actuators ADD COLUMN IF NOT EXISTS source_method TEXT;")  # bases creadas antes de la 2D
            cur.execute("TRUNCATE TABLE actuators RESTART IDENTITY CASCADE;")
            for r in records:
                cur.execute(
                    """
                    INSERT INTO actuators (
                        base_part_number, normalized_part_number, size_code, frame_size,
                        enclosure_type, power_supply, voltage_num, phase_type,
                        service_support, is_available,
                        on_off_torque_in_lbs, on_off_torque_nm, on_off_duty_cycle_pct, cycles_per_hour,
                        modulating_torque_in_lbs, modulating_torque_nm, modulating_duty_cycle_pct, starts_per_hour,
                        speed_60hz_sec, speed_50hz_sec, speed_dc_or_fixed_sec,
                        fla_60hz_amps, fla_50hz_amps, fla_dc_or_fixed_amps,
                        lra_60hz_amps, lra_50hz_amps, lra_dc_or_fixed_amps,
                        motor_power_watts, csa_certified, ce_ukca_certified,
                        hazardous_classification, table_notes, source_page, source_method
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    );
                    """,
                    (
                        r.base_part_number, r.normalized_part_number, r.size_code, r.frame_size,
                        r.enclosure_type, r.power_supply, r.voltage_num, r.phase_type,
                        r.service_support, r.is_available,
                        r.on_off_torque_in_lbs, r.on_off_torque_nm, r.on_off_duty_cycle_pct, r.cycles_per_hour,
                        r.modulating_torque_in_lbs, r.modulating_torque_nm, r.modulating_duty_cycle_pct, r.starts_per_hour,
                        r.speed_60hz_sec, r.speed_50hz_sec, r.speed_dc_or_fixed_sec,
                        r.fla_60hz_amps, r.fla_50hz_amps, r.fla_dc_or_fixed_amps,
                        r.lra_60hz_amps, r.lra_50hz_amps, r.lra_dc_or_fixed_amps,
                        r.motor_power_watts, r.csa_certified, r.ce_ukca_certified,
                        r.hazardous_classification, json.dumps(r.table_notes), r.source_page, r.source_method
                    ),
                )

        conn.commit()
    logger.info("🚀 Base de datos PostgreSQL poblada exitosamente.")
    verify_database(db_url, len(records))


def verify_database(db_url: str, n_records: int) -> None:
    """Validación final: conteos y consistencia de los datos cargados."""
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM actuators")
        a = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM actuators WHERE NOT is_available")
        na = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM users")
        u = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM actuators WHERE frame_size IN (6,7) AND csa_certified")
        bad_csa = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM actuators WHERE is_available AND on_off_torque_nm IS NULL AND modulating_torque_nm IS NULL")
        no_torque = cur.fetchone()[0]
    checks = {
        f"actuators == {n_records}": a == n_records,
        "N/A rows == 4": na == 4,
        "users >= 3": u >= 3,
        "tamaños 6/7 sin CSA": bad_csa == 0,
        "filas disponibles con torque": no_torque == 0,
    }
    for name, ok in checks.items():
        logger.info(f"{'✅' if ok else '❌'} {name}")
    logger.info(f"📊 actuators={a} (N/A={na}) users={u}")
    if not all(checks.values()):
        raise SystemExit("Validación de base de datos FALLIDA")
    logger.info("✅ VALIDACIÓN COMPLETA")


def verify_pdf_presence() -> None:
    pdf_data = DOCS_DIR / "series_76_electric_data.pdf"
    pdf_summary = DOCS_DIR / "series_76_summary.pdf"
    if pdf_data.exists():
        doc = pdfium.PdfDocument(str(pdf_data))
        logger.info(f"📄 PDF detectado: {pdf_data.name} ({len(doc)} páginas verificadas).")
    if pdf_summary.exists():
        doc_sum = pdfium.PdfDocument(str(pdf_summary))
        logger.info(f"📄 PDF detectado: {pdf_summary.name} ({len(doc_sum)} páginas verificadas).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Series 76 Ingestion & Physics Validation Pipeline")
    parser.add_argument("--mode", choices=["auto", "from-pdf", "snapshot-only"], default="auto",
                        help="auto: carga series76_catalog.json | from-pdf: re-extrae del PDF y regenera el catálogo")
    args = parser.parse_args()

    verify_pdf_presence()
    if args.mode == "from-pdf":
        run_from_pdf()
    records = load_catalog()
    save_snapshots(records)

    if args.mode != "snapshot-only":
        seed_database(records)
