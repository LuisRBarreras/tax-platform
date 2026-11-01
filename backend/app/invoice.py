"""Invoice business rules."""
import uuid
from datetime import date, datetime, timezone

from . import config
from typing import Any, Dict, List, Optional


def generate_invoice_id() -> str:
    """Generate a unique invoice id."""
    return f"INV-{uuid.uuid4()}"


def calculate_totals(items: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute subtotal, tax (always 0 for now) and total."""
    subtotal = sum((item.get("quantity", 0) or 0) * (item.get("unit-price", 0) or 0) for item in items)
    tax = 0.0  # sin impuesto por ahora
    total = subtotal + tax
    return {"subtotal": subtotal, "tax": tax, "total": total}


def build_invoice(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build a complete invoice from the request data."""
    invoice_id = generate_invoice_id()
    today = date.today().isoformat()
    totals = calculate_totals(data.get("items", []))
    return {
        "invoice-id": invoice_id,
        "invoice-number": data.get("invoice-number", ""),
        # If the UI sends no client data, fall back to the configured client.
        "client-name": data.get("client-name") or config.INVOICE_CLIENT_NAME,
        "client-email": data.get("client-email") or config.INVOICE_CLIENT_EMAIL,
        "client-address": data.get("client-address") or config.INVOICE_CLIENT_ADDRESS,
        "items": data.get("items", []),
        "subtotal": totals["subtotal"],
        "tax": totals["tax"],
        "total": totals["total"],
        "due-date": data.get("due-date"),
        "date": data.get("date") or today,
        "bank-info": data.get("bank-info"),
        "work-from": data.get("work-from", ""),
        "work-to": data.get("work-to", ""),
        "deposit-date": data.get("deposit-date", ""),
        "exchange-rate": data.get("exchange-rate"),
        "pesos": data.get("pesos"),
        "status": "created",
        "created-at": datetime.now(timezone.utc).isoformat(),
    }