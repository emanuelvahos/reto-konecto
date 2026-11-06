import os
from pathlib import Path
from decimal import Decimal
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")


def get_db_url() -> str:
    raw_url = os.getenv(
        "DATABASE_URL",
        "postgresql://konecto:konecto_secret_2026@localhost:5433/series76_db",
    ).replace("postgresql+psycopg://", "postgresql://")

    if "@db:5432" in raw_url and not Path("/.dockerenv").exists():
        host_port = os.getenv("DB_HOST_PORT", "5433")
        raw_url = raw_url.replace("@db:5432", f"@localhost:{host_port}")
    return raw_url


def sanitize_row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    clean: Dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            clean[k] = float(v)
        else:
            clean[k] = v
    return clean


def sanitize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [sanitize_row(r) for r in rows if r is not None]


@contextmanager
def get_db_cursor():
    conn = psycopg.connect(get_db_url(), row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_schema_ready = False


def ensure_schema() -> None:
    """Migración aditiva e idempotente (columnas nuevas de chat_sessions). Seguro de llamar en cada arranque."""
    global _schema_ready
    if _schema_ready:
        return
    with get_db_cursor() as cur:
        cur.execute("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS short_title TEXT;")
        cur.execute("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS cost_usd_total NUMERIC(12, 6) NOT NULL DEFAULT 0;")
    _schema_ready = True
