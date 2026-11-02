"""Application configuration.

Priority: real environment variables > backend/.env > defaults.
The .env file is loaded here, so uvicorn needs nothing exported in the shell.
"""
import os

from dotenv import load_dotenv

# Backend root (…/tax-platform/backend). Resolved before reading any setting.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# `override=False` (default): anything already exported wins.
load_dotenv(os.path.join(BACKEND_DIR, ".env"))


def get_env(key: str) -> str:
    """Read an environment variable, raising if it is missing."""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Missing environment variable: {key}")
    return value


def _bool(key: str, default: str = "0") -> bool:
    return os.environ.get(key, default).strip().lower() in {"1", "true", "yes", "on"}


def _int(key: str, default: str) -> int:
    try:
        return int(os.environ.get(key, default))
    except ValueError:
        return int(default)


# --- General ---------------------------------------------------------------
APP_NAME = "Invoice Automation Backend"
SERVER_PORT = _int("PORT", "3000")
INVOICE_STORE_PATH = os.environ.get("INVOICE_STORE_PATH", "resources/invoices.json")

# --- Files -----------------------------------------------------------------
# Relative to the process cwd: uvicorn is expected to run from `backend/`.
TMP_INVOICES_DIR = ".tmp/invoices"
PROOFS_DIR = ".tmp/proofs"
OUTBOX_DIR = ".tmp/outbox"

# --- Database (MySQL) -------------------------------------------------------
MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = _int("MYSQL_PORT", "3306")
MYSQL_USER = os.environ.get("MYSQL_USER", "tax")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "taxpass")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "tax_platform")

# --- Invoice parties (printed in the PDF; never captured by the UI) ---------
# Empty by default: real values belong in backend/.env, never in the repository.
# Issuer = who sends the invoice; client = who it is billed to.
INVOICE_ISSUER_NAME = os.environ.get("INVOICE_ISSUER_NAME", "")
INVOICE_ISSUER_ADDRESS = os.environ.get("INVOICE_ISSUER_ADDRESS", "")

INVOICE_CLIENT_NAME = os.environ.get("INVOICE_CLIENT_NAME", "")
INVOICE_CLIENT_EMAIL = os.environ.get("INVOICE_CLIENT_EMAIL", "")
INVOICE_CLIENT_ADDRESS = os.environ.get("INVOICE_CLIENT_ADDRESS", "")

# --- Email ------------------------------------------------------------------
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = _int("SMTP_PORT", "587")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "")
# Comma-separated allowlist. Empty means "nobody can receive" (safe default).
MAIL_RECIPIENTS = os.environ.get("MAIL_RECIPIENTS", "")
SMTP_DRY_RUN = _bool("SMTP_DRY_RUN", "1")  # por seguridad: por defecto NO envía

# --- Google Sheets (invoice tracker) ---------------------------------------
# Every sent invoice appends one row to the tab below. The service account
# needs the spreadsheet shared with it as Editor, and the Sheets API enabled.
GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
GOOGLE_SPREADSHEET_ID = os.environ.get("GOOGLE_SPREADSHEET_ID", "")
GOOGLE_SHEETS_TAB = os.environ.get("GOOGLE_SHEETS_TAB", "Copy of 2026")
GOOGLE_SHEETS_GID = os.environ.get("GOOGLE_SHEETS_GID", "")  # optional: link to the tab
GOOGLE_SHEETS_ENABLED = _bool("GOOGLE_SHEETS_ENABLED", "1")
GOOGLE_DOC_TEMPLATE_ID = os.environ.get("GOOGLE_DOC_TEMPLATE_ID", "")
