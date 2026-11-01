"""SQLite storage for invoice metadata.

PDFs stay on disk (`.tmp/invoices/`); the `pdf_path` column keeps their location,
so moving the files to S3 later only means changing that value (a key) and the
code that writes/reads it. The schema itself does not change.
"""
import sqlite3
from pathlib import Path
from typing import Iterator
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id             TEXT PRIMARY KEY,
    number         TEXT NOT NULL DEFAULT '',
    client_name    TEXT NOT NULL,
    client_email   TEXT NOT NULL,
    client_address TEXT NOT NULL DEFAULT '',
    date           TEXT NOT NULL,
    due_date       TEXT NOT NULL DEFAULT '',
    subtotal       REAL NOT NULL DEFAULT 0,
    tax            REAL NOT NULL DEFAULT 0,
    total          REAL NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'created',
    bank_info      TEXT NOT NULL DEFAULT '',
    items_json     TEXT NOT NULL DEFAULT '[]',
    work_from      TEXT NOT NULL DEFAULT '',
    work_to        TEXT NOT NULL DEFAULT '',
    deposit_date   TEXT NOT NULL DEFAULT '',
    exchange_rate  REAL,
    pesos          REAL,   -- override manual; NULL = total * exchange_rate
    pdf_path       TEXT,
    proof_path     TEXT,
    sent_at        TEXT,
    sent_to        TEXT,
    created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices (date DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_invoices_created ON invoices (created_at DESC);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """One connection per operation: FastAPI runs each request in its own thread."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create the directory, the schema and run simple migrations (idempotent)."""
    Path(config.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Add new columns to existing databases (SQLite has no ADD COLUMN IF NOT EXISTS)."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(invoices)")}
    for column, definition in (
        ("proof_path", "TEXT"),
        ("work_from", "TEXT NOT NULL DEFAULT ''"),
        ("work_to", "TEXT NOT NULL DEFAULT ''"),
        ("deposit_date", "TEXT NOT NULL DEFAULT ''"),
        ("exchange_rate", "REAL"),
        ("pesos", "REAL"),
        ("number", "TEXT NOT NULL DEFAULT ''"),
        ("sent_at", "TEXT"),
        ("sent_to", "TEXT"),
    ):
        if column not in existing:
            conn.execute(f"ALTER TABLE invoices ADD COLUMN {column} {definition}")
            print(f"DB migrated: +{column}")
