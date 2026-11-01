"""Copy invoices from the old SQLite database into MySQL.

One-off migration. Reads `backend/data/invoices.db` when it exists and inserts every
row into MySQL (idempotent: rows already present are skipped).

Usage:  cd backend && ./.venv/bin/python scripts/migrate_sqlite_to_mysql.py
"""
import json
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app import config, invoice_store  # noqa: E402

SQLITE_PATH = BACKEND_DIR / "data" / "invoices.db"


def read_sqlite() -> list[dict]:
    if not SQLITE_PATH.exists():
        print(f"No SQLite database at {SQLITE_PATH}, nothing to migrate.")
        return []

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    rows = [dict(row) for row in conn.execute("SELECT * FROM invoices")]
    conn.close()
    print(f"SQLite: found {len(rows)} invoices")
    return rows


def to_invoice(row: dict) -> dict:
    """Map a SQLite row to the dict shape the store expects."""
    return {
        "invoice-id": row["id"],
        "invoice-number": row["number"],
        "client-name": row["client_name"],
        "client-email": row["client_email"],
        "client-address": row["client_address"],
        "items": json.loads(row["items_json"] or "[]"),
        "subtotal": row["subtotal"],
        "tax": row["tax"],
        "total": row["total"],
        "due-date": row["due_date"],
        "date": row["date"],
        "bank-info": row["bank_info"],
        "status": row["status"],
        "pdf-path": row["pdf_path"],
        "proof-path": row["proof_path"],
        "work-from": row["work_from"],
        "work-to": row["work_to"],
        "deposit-date": row["deposit_date"],
        "exchange-rate": row["exchange_rate"],
        "pesos": row["pesos"],
        "sent-at": row["sent_at"],
        "sent-to": row["sent_to"],
        "created-at": row["created_at"],
    }


def main() -> int:
    rows = read_sqlite()
    if not rows:
        return 0

    inserted = skipped = 0
    for row in rows:
        invoice = to_invoice(row)
        if invoice_store.get_invoice(invoice["invoice-id"]) is not None:
            skipped += 1
            continue
        invoice_store.save_invoice(invoice)
        inserted += 1

    total = len(invoice_store.get_all_invoices())
    print(f"\nInserted: {inserted} | Already present: {skipped} | Total in MySQL: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
