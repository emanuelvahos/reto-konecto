import os
from pathlib import Path
import pytest
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

# Cargar variables de entorno desde la raíz del proyecto
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")


def get_test_db_url() -> str:
    """Resuelve automáticamente la conexión tanto desde Windows host (5433) como dentro de Docker (db:5432)."""
    raw_url = os.getenv(
        "DATABASE_URL",
        "postgresql://konecto:konecto_secret_2026@localhost:5433/series76_db",
    ).replace("postgresql+psycopg://", "postgresql://")

    # Si corremos pytest desde fuera de Docker en Windows/Linux host, traducir @db:5432 -> @localhost:DB_HOST_PORT
    if "@db:5432" in raw_url and not Path("/.dockerenv").exists():
        host_port = os.getenv("DB_HOST_PORT", "5433")
        raw_url = raw_url.replace("@db:5432", f"@localhost:{host_port}")
    return raw_url


@pytest.fixture(scope="module")
def db_conn():
    conn = psycopg.connect(get_test_db_url(), row_factory=dict_row)
    yield conn
    conn.close()


# =====================================================================
# 1. CONTEOS EXACTOS POR TABLA DEL PDF
# =====================================================================
def test_total_catalog_counts_per_table(db_conn):
    """Verifica que las 6 tablas del PDF sumen exactamente 68 filas con su desglose exacto."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT enclosure_type, power_supply, service_support, COUNT(*) as total
            FROM actuators
            GROUP BY enclosure_type, power_supply, service_support
            ORDER BY enclosure_type, power_supply;
            """
        )
        rows = {(r["enclosure_type"], r["power_supply"], r["service_support"]): r["total"] for r in cur.fetchall()}

    assert sum(rows.values()) == 68, f"Se esperaban 68 filas totales, hay {sum(rows.values())}"
    assert rows[("Weatherproof", "110V Single Phase", "Both On/Off & Modulating")] == 11
    assert rows[("Weatherproof", "220V Single Phase", "Both On/Off & Modulating")] == 16
    assert rows[("Weatherproof", "220V 3 Phase", "Both On/Off & Modulating")] == 7
    assert rows[("Weatherproof", "220V 3 Phase", "N/A (Not Available in 220V 3-Phase)")] == 4
    assert rows[("Explosionproof", "24V AC/DC", "On/Off Only")] == 5
    assert rows[("Explosionproof", "24V DC", "Modulating Only")] == 5
    assert rows[("Explosionproof", "110V Single Phase", "Both On/Off & Modulating")] == 10
    assert rows[("Explosionproof", "220V Single Phase", "Both On/Off & Modulating")] == 10


# =====================================================================
# 2. AUDITORÍA CONTRA ERRORES DE OCR EN PART NUMBERS
# =====================================================================
def test_no_ocr_corrupted_part_numbers(db_conn):
    """Garantiza que ningún error de OCR del PDF original se haya filtrado a la base de datos."""
    forbidden_ocr_typos = [
        "761800", "762400", "762800", "763800", "763000",
        "764400", "764800", "765800", "766400", "766800",
        "767800", "767000", "761730", "11330000", "113000000",
    ]
    with db_conn.cursor() as cur:
        cur.execute("SELECT base_part_number FROM actuators;")
        all_parts = [r["base_part_number"] for r in cur.fetchall()]

    for part in all_parts:
        for typo in forbidden_ocr_typos:
            assert typo not in part, f"Se detectó residuo de OCR '{typo}' en el part number '{part}'"
        assert part.endswith("/A"), f"El part number '{part}' no termina en '/A'"


# =====================================================================
# 3. LEYES FÍSICAS Y PROPAGACIÓN DE ROWSPANS (MOTOR POWER)
# =====================================================================
def test_motor_power_rowspan_propagation(db_conn):
    """Verifica que todas las 64 filas disponibles tengan Motor Power resuelto y dentro del dominio válido."""
    valid_wattages = {15, 40, 90, 180, 700}
    with db_conn.cursor() as cur:
        cur.execute("SELECT base_part_number, motor_power_watts FROM actuators WHERE is_available = TRUE;")
        rows = cur.fetchall()

    assert len(rows) == 64
    for r in rows:
        assert r["motor_power_watts"] in valid_wattages, (
            f"Motor power inválido ({r['motor_power_watts']}) en {r['base_part_number']}"
        )


def test_physical_torque_ratio_and_current_laws(db_conn):
    """Verifica que en las 64 filas activas In-Lbs / Nm esté en [8.2, 9.5] y que LRA >= FLA."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT * FROM actuators WHERE is_available = TRUE;")
        rows = cur.fetchall()

    for r in rows:
        if r["on_off_torque_in_lbs"] and r["on_off_torque_nm"]:
            ratio = float(r["on_off_torque_in_lbs"]) / float(r["on_off_torque_nm"])
            assert 8.2 <= ratio <= 9.5, f"Ratio On/Off inválido en {r['base_part_number']}: {ratio}"

        if r["modulating_torque_in_lbs"] and r["modulating_torque_nm"]:
            ratio = float(r["modulating_torque_in_lbs"]) / float(r["modulating_torque_nm"])
            assert 8.2 <= ratio <= 9.5, f"Ratio Modulating inválido en {r['base_part_number']}: {ratio}"

        for fla_col, lra_col in [
            ("fla_60hz_amps", "lra_60hz_amps"),
            ("fla_50hz_amps", "lra_50hz_amps"),
            ("fla_dc_or_fixed_amps", "lra_dc_or_fixed_amps"),
        ]:
            if r[fla_col] is not None and r[lra_col] is not None:
                assert float(r[lra_col]) >= float(r[fla_col]), (
                    f"LRA < FLA en {r['base_part_number']} ({fla_col}={r[fla_col]}, {lra_col}={r[lra_col]})"
                )


# =====================================================================
# 4. SPOT-CHECKS QUIRÚRGICOS DE LAS TRAMPAS DEL PDF
# =====================================================================
def test_spot_check_3phase_frequency_columns(db_conn):
    """Pág 2 (220V 3-Phase, orden 60 Hz | 50 Hz como en todas las tablas): spot-check de 763A00-11330C00/A."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM actuators WHERE base_part_number = '763A00-11330C00/A' AND power_supply = '220V 3 Phase';"
        )
        row = cur.fetchone()

    assert row is not None
    assert float(row["speed_50hz_sec"]) == 32.0
    assert float(row["speed_60hz_sec"]) == 26.0
    assert float(row["fla_60hz_amps"]) == 1.0
    assert float(row["lra_60hz_amps"]) == 1.2
    assert row["motor_power_watts"] == 40


def test_spot_check_explosionproof_ocr_traps(db_conn):
    """Pág 4: spot-check de 764X30-11300000/A (800 Nm, LRA 60/50 Hz) y 763Y30-11320000/A (FLA 60/50 Hz)."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT * FROM actuators WHERE base_part_number = '764X30-11300000/A';")
        r110 = cur.fetchone()
        cur.execute("SELECT * FROM actuators WHERE base_part_number = '763Y30-11320000/A';")
        r220 = cur.fetchone()

    assert float(r110["on_off_torque_nm"]) == 800.0
    assert float(r110["lra_50hz_amps"]) == 7.4
    assert float(r110["lra_60hz_amps"]) == 7.3

    assert float(r220["fla_50hz_amps"]) == 1.5
    assert float(r220["fla_60hz_amps"]) == 1.9


def test_csa_certification_edge_case_sizes_6_and_7(db_conn):
    """Pág 1 Nota al pie: Sizes 6 and 7 are not CSA Certified."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT base_part_number, frame_size FROM actuators WHERE csa_certified = FALSE AND is_available = TRUE;")
        non_csa = cur.fetchall()

    part_numbers = {r["base_part_number"] for r in non_csa}
    expected = {
        "766A00-11320000/A",
        "766B00-11320000/A",
        "767A00-11320000/A",
        "767B00-11320000/A",
        "767C00-11320000/A",
    }
    assert part_numbers == expected


# =====================================================================
# 5. BÚSQUEDA DIFUSA (pg_trgm) Y VECTORES (pgvector)
# =====================================================================
def test_fuzzy_search_pg_trgm_recovers_typo(db_conn):
    """Si el usuario ingresa '761800-11300000/A' (error de dedo B->8), pg_trgm debe sugerir '761B00-11300000/A'."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT base_part_number, similarity(base_part_number, '761800-11300000/A') AS sim
            FROM actuators
            ORDER BY sim DESC
            LIMIT 1;
            """
        )
        best = cur.fetchone()

    assert best is not None
    assert best["base_part_number"] in ("761B00-11300000/A", "761A00-11300000/A")
    # Un solo carácter distinto en trigramas da ~0.67; umbral 0.5 es robusto y muy superior al default de pg_trgm (0.3).
    assert float(best["sim"]) > 0.5


def test_knowledge_chunks_embeddings_populated(db_conn):
    """Verifica que los 4 chunks de conocimiento tengan su vector de embedding no nulo con la dimensión de .env."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(embedding) AS n FROM knowledge_chunks;")
        if cur.fetchone()["n"] == 0:
            pytest.skip("Embeddings desactivados (ingest sin --with-embeddings); pgvector se retira en la Fase 2")
    expected_dim = int(os.getenv("EMBEDDING_DIMENSIONS", "2048"))
    with db_conn.cursor() as cur:
        cur.execute("SELECT chunk_key, vector_dims(embedding) as dims FROM knowledge_chunks;")
        rows = cur.fetchall()

    assert len(rows) == 4
    for r in rows:
        assert r["dims"] == expected_dim, f"Chunk {r['chunk_key']} tiene dim {r['dims']} != {expected_dim}"