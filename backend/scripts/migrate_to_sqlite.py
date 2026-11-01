"""Migrate existing invoices into SQLite.

Source: MongoDB when reachable (where they used to live), otherwise the JSON
files in .tmp/invoices/. Idempotent: INSERT OR IGNORE per id.

Usage:  cd backend && ./.venv/bin/python scripts/migrate_to_sqlite.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app import config, db  # noqa: E402


def from_mongo() -> list[dict]:
    try:
        from pymongo import MongoClient
    except ImportError:
        return []

    try:
        client = MongoClient(config.MONGO_URL if hasattr(config, "MONGO_URL")
                             else "mongodb://127.0.0.1:27017",
                             serverSelectionTimeoutMS=1500)
        docs = list(client["tax_platform"]["invoices"].find({}, {"_id": 0}))
        client.close()
        print(f"MongoDB: found {len(docs)} invoices")
        return docs
    except Exception as exc:  # Mongo down or driver missing
        print(f"MongoDB unavailable ({exc.__class__.__name__}), falling back to JSON")
        return []


def from_json() -> list[dict]:
    source = Path(config.TMP_INVOICES_DIR)
    if not source.exists():
        return []
    docs = []
    for path in sorted(source.glob("*.json")):
        invoice = json.loads(path.read_text(encoding="utf-8"))
        invoice.setdefault(
            "created-at",
            datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        )
        docs.append(invoice)
    print(f"JSON: found {len(docs)} files")
    return docs


def main() -> int:
    invoices = from_mongo() or from_json()
    if not invoices:
        print("Nothing to migrate.")
        return 0

    inserted = 0
    for invoice in invoices:
        invoice_id = invoice.get("invoice-id")
        if not invoice_id:
            continue
        if db_exists(invoice_id):
            continue
        invoice.setdefault("created-at", datetime.now(timezone.utc).isoformat())
        insert(invoice)
        inserted += 1
        print(f"  + {invoice_id}")

    print(f"\nInserted: {inserted} | Total in SQLite: {count()}")
    return 0


def db_exists(invoice_id: str) -> bool:
    with db.connection() as conn:
        return conn.execute("SELECT 1 FROM invoices WHERE id = ?", (invoice_id,)).fetchone() is not None


def insert(invoice: dict) -> None:
    values = {
        "id": invoice["invoice-id"],
        "client_name": invoice.get("client-name", ""),
        "client_email": invoice.get("client-email", ""),
        "client_address": invoice.get("client-address", ""),
        "date": invoice.get("date", ""),
        "due_date": invoice.get("due-date", ""),
        "subtotal": invoice.get("subtotal", 0),
        "tax": invoice.get("tax", 0),
        "total": invoice.get("total", 0),
        "status": invoice.get("status", "created"),
        "bank_info": invoice.get("bank-info", ""),
        "items_json": json.dumps(invoice.get("items", []), ensure_ascii=False),
        "pdf_path": f"{config.TMP_INVOICES_DIR}/{invoice['invoice-id']}.pdf",
        "created_at": invoice.get("created-at", ""),
    }
    columns = ", ".join(values)
    placeholders = ", ".join(f":{c}" for c in values)
    with db.connection() as conn:
        conn.execute(
            f"INSERT OR IGNORE INTO invoices ({columns}) VALUES ({placeholders})", values
        )


def count() -> int:
    with db.connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]


if __name__ == "__main__":
    raise SystemExit(main())
