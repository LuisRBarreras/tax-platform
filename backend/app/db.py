"""MySQL storage for invoice metadata.

PDFs stay on disk (`.tmp/invoices/`); the `pdf_path` column keeps their location,
so moving the files to S3 later only means changing that value (a key) and the
code that writes/reads it. The schema itself does not change.
"""
from contextlib import contextmanager
from typing import Any, Dict, Iterator

import pymysql
from pymysql.cursors import DictCursor

from . import config

# VARCHAR sizes keep MySQL happy: TEXT columns cannot have a DEFAULT.
SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id             VARCHAR(64)  NOT NULL PRIMARY KEY,
    number         VARCHAR(64)  NOT NULL DEFAULT '',
    client_name    VARCHAR(255) NOT NULL DEFAULT '',
    client_email   VARCHAR(255) NOT NULL DEFAULT '',
    client_address VARCHAR(500) NOT NULL DEFAULT '',
    date           CHAR(10)     NOT NULL DEFAULT '',
    due_date       CHAR(10)     NOT NULL DEFAULT '',
    subtotal       DECIMAL(12,2) NOT NULL DEFAULT 0,
    tax            DECIMAL(12,2) NOT NULL DEFAULT 0,
    total          DECIMAL(12,2) NOT NULL DEFAULT 0,
    status         VARCHAR(20)  NOT NULL DEFAULT 'created',
    bank_info      VARCHAR(500) NOT NULL DEFAULT '',
    items_json     TEXT         NULL,
    pdf_path       VARCHAR(500) NULL,
    proof_path     VARCHAR(500) NULL,
    work_from      CHAR(10)     NOT NULL DEFAULT '',
    work_to        CHAR(10)     NOT NULL DEFAULT '',
    deposit_date   CHAR(10)     NOT NULL DEFAULT '',
    exchange_rate  DECIMAL(12,4) NULL,
    pesos          DECIMAL(14,2) NULL,
    sent_at        VARCHAR(40)  NULL,
    sent_to        VARCHAR(255) NULL,
    created_at     VARCHAR(40)  NOT NULL DEFAULT '',
    INDEX idx_invoices_created (created_at),
    INDEX idx_invoices_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# Invoices received by mail (the "honorarios" to pay), one row per email.
PAYABLES_SCHEMA = """
CREATE TABLE IF NOT EXISTS payables (
    id               VARCHAR(64)  NOT NULL PRIMARY KEY,
    message_id       VARCHAR(255) NOT NULL,
    subject          VARCHAR(255) NOT NULL DEFAULT '',
    sender           VARCHAR(255) NOT NULL DEFAULT '',
    received_at      VARCHAR(40)  NOT NULL DEFAULT '',
    folio            VARCHAR(32)  NOT NULL DEFAULT '',
    total            DECIMAL(12,2) NULL,
    subtotal         DECIMAL(12,2) NULL,
    currency         CHAR(3)      NOT NULL DEFAULT 'MXN',
    cfdi_fecha       CHAR(10)     NOT NULL DEFAULT '',
    period           VARCHAR(7)   NOT NULL DEFAULT '',
    cfdi_uuid        VARCHAR(64)  NOT NULL DEFAULT '',
    issuer_name      VARCHAR(255) NOT NULL DEFAULT '',
    issuer_rfc       VARCHAR(20)  NOT NULL DEFAULT '',
    pdf_path         VARCHAR(500) NULL,
    xml_path         VARCHAR(500) NULL,
    status           VARCHAR(20)  NOT NULL DEFAULT 'pending',
    replied_at       VARCHAR(40)  NULL,
    reply_message_id VARCHAR(255) NULL,
    paid_at          VARCHAR(40)  NULL,
    proof_path       VARCHAR(500) NULL,
    created_at       VARCHAR(40)  NOT NULL DEFAULT '',
    UNIQUE KEY uniq_payables_message (message_id),
    INDEX idx_payables_status (status),
    INDEX idx_payables_received (received_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# Payables columns added later (the table predates them on existing databases).
PAYABLES_MIGRATIONS = (
    ("period", "VARCHAR(7) NOT NULL DEFAULT ''"),
)

# Columns added after the first release: created on the fly for older databases.
MIGRATIONS = (
    ("number", "VARCHAR(64) NOT NULL DEFAULT ''"),
    ("proof_path", "VARCHAR(500) NULL"),
    ("work_from", "CHAR(10) NOT NULL DEFAULT ''"),
    ("work_to", "CHAR(10) NOT NULL DEFAULT ''"),
    ("deposit_date", "CHAR(10) NOT NULL DEFAULT ''"),
    ("exchange_rate", "DECIMAL(12,4) NULL"),
    ("pesos", "DECIMAL(14,2) NULL"),
    ("sent_at", "VARCHAR(40) NULL"),
    ("sent_to", "VARCHAR(255) NULL"),
)


def get_connection() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
        connect_timeout=5,
    )


@contextmanager
def connection() -> Iterator[pymysql.connections.Connection]:
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


def _existing_columns(
    conn: pymysql.connections.Connection, table: str = "invoices"
) -> set[str]:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
            (config.MYSQL_DATABASE, table),
        )
        return {row["COLUMN_NAME"] for row in cursor.fetchall()}


def init_db() -> None:
    """Create the table and apply simple migrations (idempotent)."""
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(SCHEMA)
            cursor.execute(PAYABLES_SCHEMA)

        existing = _existing_columns(conn)
        for column, definition in MIGRATIONS:
            if column not in existing:
                with conn.cursor() as cursor:
                    cursor.execute(f"ALTER TABLE invoices ADD COLUMN {column} {definition}")
                print(f"DB migrated: +{column}")

        existing_payables = _existing_columns(conn, "payables")
        for column, definition in PAYABLES_MIGRATIONS:
            if column not in existing_payables:
                with conn.cursor() as cursor:
                    cursor.execute(f"ALTER TABLE payables ADD COLUMN {column} {definition}")
                    cursor.execute(
                        "UPDATE payables SET period = "
                        "DATE_FORMAT(DATE_SUB(cfdi_fecha, INTERVAL 1 MONTH), '%Y-%m') "
                        "WHERE cfdi_fecha <> '' AND period = ''"
                    )
                print(f"DB migrated: payables +{column}")


def wait_for_db(retries: int = 30, delay: float = 1.0) -> bool:
    """Block until MySQL answers (used by the container entrypoint)."""
    import time

    for attempt in range(retries):
        try:
            conn = get_connection()
            conn.close()
            return True
        except pymysql.err.OperationalError:
            if attempt == retries - 1:
                return False
            time.sleep(delay)
    return False
