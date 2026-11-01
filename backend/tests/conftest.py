"""Shared fixtures.

Every test runs against a throwaway MySQL database (`tax_platform_test`) and a
temporary working directory. The database is dropped and the directory removed when
the session ends, so nothing leaks into the development database.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pymysql

# --- isolate the environment BEFORE importing app modules -------------------
_TMP = Path(tempfile.mkdtemp(prefix="tax-platform-tests-"))

os.environ["MYSQL_DATABASE"] = "tax_platform_test"
os.environ["SMTP_DRY_RUN"] = "1"
os.environ["MAIL_RECIPIENTS"] = "billing@example.com,other@example.com"
os.environ["INVOICE_ISSUER_NAME"] = "Test Issuer"
os.environ["INVOICE_ISSUER_ADDRESS"] = "1 Test Street\nTestville"
os.environ["INVOICE_CLIENT_NAME"] = "Test Client LLC"
os.environ["INVOICE_CLIENT_EMAIL"] = "client@example.com"
os.environ["INVOICE_CLIENT_ADDRESS"] = "100 Client Road\nClientville"

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import pytest  # noqa: E402

from app import config, db  # noqa: E402


def _server_connection():
    """Connection without a database, to create/drop the test schema."""
    return pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        autocommit=True,
        connect_timeout=5,
    )


def _ensure_test_database() -> None:
    with _server_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS {config.MYSQL_DATABASE} "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )


_ensure_test_database()


def pytest_sessionfinish(session, exitstatus):
    """Clean-up: drop the test database and remove the temporary directory."""
    try:
        with _server_connection() as conn, conn.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS {config.MYSQL_DATABASE}")
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def workdir():
    """Relative paths (.tmp/...) resolve against the cwd: keep them inside the sandbox."""
    previous = Path.cwd()
    os.chdir(_TMP)
    yield _TMP
    os.chdir(previous)


@pytest.fixture()
def clean_db():
    """Empty the invoices table before each test that touches the store."""
    with db.connection() as conn, conn.cursor() as cursor:
        cursor.execute("DELETE FROM invoices")
    yield


@pytest.fixture()
def sample_invoice():
    from app.invoice import build_invoice

    return build_invoice(
        {
            "invoice-number": "2026-001",
            "date": "2026-10-30",
            "work-from": "2026-10-16",
            "work-to": "2026-10-31",
            "deposit-date": "2026-10-30",
            "exchange-rate": 18.5,
            "items": [{"description": "Software Service", "quantity": 1, "unit-price": 1000}],
        }
    )


@pytest.fixture()
def tmp_dir():
    return _TMP


@pytest.fixture()
def settings():
    return config
