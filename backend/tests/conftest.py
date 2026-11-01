"""Shared fixtures.

Every test runs against a throwaway SQLite database and a temporary working
directory, so the real `data/invoices.db` and `.tmp/` are never touched.
"""
import os
import sys
import tempfile
from pathlib import Path

# --- isolate the environment BEFORE importing app modules -------------------
# config reads these at import time, and invoice_store creates the schema then.
_TMP = Path(tempfile.mkdtemp(prefix="tax-platform-tests-"))
os.environ["DATABASE_PATH"] = str(_TMP / "test.db")
os.environ["SMTP_DRY_RUN"] = "1"
os.environ["MAIL_RECIPIENTS"] = "billing@example.com,other@example.com"
os.environ["INVOICE_ISSUER_NAME"] = "Test Issuer"
os.environ["INVOICE_ISSUER_ADDRESS"] = "1 Test Street\nTestville"
os.environ["INVOICE_CLIENT_NAME"] = "Test Client LLC"
os.environ["INVOICE_CLIENT_EMAIL"] = "client@example.com"
os.environ["INVOICE_CLIENT_ADDRESS"] = "100 Client Road\nClientville"

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Relative paths (.tmp/...) resolve against the cwd: keep them inside the sandbox.
os.chdir(_TMP)

import pytest  # noqa: E402

from app import config, db  # noqa: E402


@pytest.fixture()
def clean_db():
    """Empty the invoices table before each test that touches the store."""
    with db.connection() as conn:
        conn.execute("DELETE FROM invoices")
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
