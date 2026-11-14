"""Storage for the invoices received by mail (the "honorarios" to pay).

One row per email from the billing address. Attachments pulled from the mailbox
live in `.tmp/payables/`; the row only keeps their paths, like invoices do.
"""
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from . import db

COLUMNS = (
    "id", "message_id", "subject", "sender", "received_at", "folio", "total",
    "subtotal", "currency", "cfdi_fecha", "period", "cfdi_uuid", "issuer_name", "issuer_rfc",
    "pdf_path", "xml_path", "status", "replied_at", "reply_message_id", "paid_at",
    "proof_path", "created_at",
)

# NOT NULL columns need a value even when the email does not carry one.
DEFAULTS = {
    "message_id": "",
    "subject": "",
    "sender": "",
    "received_at": "",
    "folio": "",
    "currency": "MXN",
    "cfdi_fecha": "",
    "period": "",
    "cfdi_uuid": "",
    "issuer_name": "",
    "issuer_rfc": "",
    "status": "pending",
}

# Pending first, then the newest: what still owes money is what matters.
ORDER = "ORDER BY (status = 'paid') ASC, received_at DESC"


def row_id(message_id: str) -> str:
    """Stable, short id derived from the email: HON-<16 hex>."""
    digest = hashlib.sha1(message_id.strip().encode("utf-8")).hexdigest()[:16]
    return f"HON-{digest}"


def period_for(iso_date: str) -> str:
    """'2026-11-12' -> '2026-10': the invoice covers the previous month.

    The accountant issues them at the start of the month for the month that
    just ended (3133 on Nov 12 is October's honorarios).
    """
    try:
        stamp = datetime.strptime(str(iso_date)[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return ""
    year, month = (stamp.year, stamp.month - 1) if stamp.month > 1 else (stamp.year - 1, 12)
    return f"{year:04d}-{month:02d}"


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value) if isinstance(value, Decimal) else value


def _row_to_payable(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "message-id": row["message_id"],
        "subject": row["subject"],
        "sender": row["sender"],
        "received-at": row["received_at"],
        "folio": row["folio"],
        "total": _num(row["total"]),
        "subtotal": _num(row["subtotal"]),
        "currency": row["currency"],
        "cfdi-fecha": row["cfdi_fecha"],
        "period": row["period"],
        "cfdi-uuid": row["cfdi_uuid"],
        "issuer-name": row["issuer_name"],
        "issuer-rfc": row["issuer_rfc"],
        "pdf-path": row["pdf_path"],
        "xml-path": row["xml_path"],
        "status": row["status"],
        "replied-at": row["replied_at"],
        "reply-message-id": row["reply_message_id"],
        "paid-at": row["paid_at"],
        "proof-path": row["proof_path"],
        "created-at": row["created_at"],
    }


def save_payable(payable: Dict[str, Any]) -> Dict[str, Any]:
    """Insert or refresh one row. Existing status/paid fields are preserved."""
    payable = {**payable}
    payable.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    # Always derived here, so no caller can store an invoice without a period.
    if not payable.get("period"):
        payable["period"] = period_for(
            payable.get("cfdi_fecha") or payable.get("received_at") or ""
        )
    values = [
        payable.get(column) if payable.get(column) is not None else DEFAULTS.get(column)
        for column in COLUMNS
    ]

    updates = ", ".join(
        f"{column} = new.{column}"
        for column in COLUMNS
        if column not in ("id", "created_at", "status", "paid_at", "proof_path")
    )
    placeholders = ", ".join(["%s"] * len(COLUMNS))

    with db.connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO payables ({', '.join(COLUMNS)}) VALUES ({placeholders}) "
            f"AS new ON DUPLICATE KEY UPDATE {updates}",
            values,
        )

    saved = get_payable(payable["id"])
    assert saved is not None
    return saved


def get_payable(payable_id: str) -> Optional[Dict[str, Any]]:
    with db.connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT * FROM payables WHERE id = %s", (payable_id,))
        row = cursor.fetchone()
    return _row_to_payable(row) if row else None


def list_payables(status: str = "", limit: int = 200) -> List[Dict[str, Any]]:
    """Deleted rows are hidden unless they are asked for by name."""
    query = "SELECT * FROM payables"
    params: List[Any] = []
    if status:
        query += " WHERE status = %s"
        params.append(status)
    elif status != "deleted":
        query += " WHERE status <> 'deleted'"
    query += f" {ORDER} LIMIT %s"
    params.append(max(1, min(limit, 500)))

    with db.connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, params)
        return [_row_to_payable(row) for row in cursor.fetchall()]


def count_by_status() -> Dict[str, int]:
    with db.connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT status, COUNT(*) AS n FROM payables WHERE status <> 'deleted' "
            "GROUP BY status"
        )
        return {row["status"]: int(row["n"]) for row in cursor.fetchall()}


def known_message_ids() -> set:
    """Every Message-ID ever seen, deleted included: a sync must not resurrect them."""
    with db.connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT message_id FROM payables")
        return {row["message_id"] for row in cursor.fetchall()}


def mark_replied(payable_id: str, replied_at: str, reply_message_id: str = "") -> None:
    """The invoice answered: the payment email went out."""
    with db.connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE payables SET status = 'paid', replied_at = %s, reply_message_id = %s, "
            "paid_at = COALESCE(paid_at, %s) WHERE id = %s",
            (replied_at, reply_message_id, replied_at, payable_id),
        )


def set_proof(payable_id: str, path: str) -> None:
    with db.connection() as conn, conn.cursor() as cursor:
        cursor.execute("UPDATE payables SET proof_path = %s WHERE id = %s", (path, payable_id))


def set_status(payable_id: str, status: str, paid_at: str = "") -> None:
    with db.connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE payables SET status = %s, paid_at = %s WHERE id = %s",
            (status, paid_at or None, payable_id),
        )


db.init_db()
