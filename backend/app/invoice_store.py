"""Invoice storage: metadata in SQLite, PDFs on disk."""
import json
import re
from typing import Any, Dict, List, Optional

from . import db

INVOICE_ID_RE = re.compile(r"^INV-[A-Za-z0-9-]{1,80}$")

# table columns -> JSON keys exposed by the API
COLUMNS = (
    "id", "number", "client_name", "client_email", "client_address", "date", "due_date",
    "subtotal", "tax", "total", "status", "bank_info", "items_json", "pdf_path",
    "proof_path", "work_from", "work_to", "deposit_date", "exchange_rate", "pesos",
    "sent_at", "sent_to", "created_at",
)


def is_valid_invoice_id(invoice_id: str) -> bool:
    """Reject unexpected ids and keep the expected format."""
    return bool(INVOICE_ID_RE.match(invoice_id))


def _row_to_invoice(row: Dict[str, Any]) -> Dict[str, Any]:
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


def save_invoice(invoice: Dict[str, Any]) -> Dict[str, Any]:
    """Insert or update the invoice (id is the primary key)."""
    values = {
        "id": invoice["invoice-id"],
        "number": invoice.get("invoice-number", ""),
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
        "pdf_path": invoice.get("pdf-path"),
        "proof_path": invoice.get("proof-path"),
        "work_from": invoice.get("work-from", ""),
        "work_to": invoice.get("work-to", ""),
        "deposit_date": invoice.get("deposit-date", ""),
        "exchange_rate": invoice.get("exchange-rate"),
        "pesos": invoice.get("pesos"),
        "sent_at": invoice.get("sent-at"),
        "sent_to": invoice.get("sent-to"),
        "created_at": invoice.get("created-at", ""),
    }

    placeholders = ", ".join(f":{c}" for c in COLUMNS)
    updates = ", ".join(f"{c} = excluded.{c}" for c in COLUMNS if c != "id")

    with db.connection() as conn:
        conn.execute(
            f"INSERT INTO invoices ({', '.join(COLUMNS)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            values,
        )

    print(f"Invoice saved to SQLite: {values['id']}")
    return invoice


def mark_sent(invoice_id: str, to: str, sent_at: str) -> None:
    """Mark the invoice as sent."""
    with db.connection() as conn:
        conn.execute(
            "UPDATE invoices SET status = 'sent', sent_at = ?, sent_to = ? WHERE id = ?",
            (sent_at, to, invoice_id),
        )


def set_proof_path(invoice_id: str, proof_path: Optional[str]) -> None:
    """Store the uploaded proof path (None clears it)."""
    with db.connection() as conn:
        conn.execute("UPDATE invoices SET proof_path = ? WHERE id = ?", (proof_path, invoice_id))


def set_pdf_path(invoice_id: str, pdf_path: str) -> None:
    """Store where the PDF lives (a local path today, an S3 key tomorrow)."""
    with db.connection() as conn:
        conn.execute("UPDATE invoices SET pdf_path = ? WHERE id = ?", (pdf_path, invoice_id))


def get_all_invoices() -> List[Dict[str, Any]]:
    """All invoices, newest first."""
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT * FROM invoices ORDER BY created_at DESC, date DESC"
        ).fetchall()
    return [_row_to_invoice(dict(row)) for row in rows]


def get_invoices_page(page: int = 1, per_page: int = 10) -> tuple[List[Dict[str, Any]], int]:
    """One page of invoices (newest first) plus the total record count."""
    offset = (page - 1) * per_page
    with db.connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM invoices ORDER BY created_at DESC, date DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
    return [_row_to_invoice(dict(row)) for row in rows], total


def get_invoice(invoice_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single invoice by id."""
    if not is_valid_invoice_id(invoice_id):
        return None

    with db.connection() as conn:
        row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()

    return _row_to_invoice(dict(row)) if row else None


def delete_invoice(invoice_id: str) -> bool:
    """Delete the row (the PDF on disk is left alone)."""
    if not is_valid_invoice_id(invoice_id):
        return False
    with db.connection() as conn:
        cur = conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    return cur.rowcount == 1


db.init_db()
