"""PDF generation from the HTML template using WeasyPrint."""
from datetime import datetime

from . import config
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Directories
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "resources" / "template"
TEMPLATE_FILE = "invoice.html"

INVOICES_DIR = Path(".tmp") / "invoices"


def ensure_tmp_invoices_dir() -> None:
    """Create .tmp/invoices if it does not exist yet."""
    INVOICES_DIR.mkdir(parents=True, exist_ok=True)


def _money(value: Any) -> str:
    """1250.0 -> $1,250.00"""
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _qty(value: Any) -> str:
    """1.0 -> 1 ; 2.5 -> 2.5"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "0"
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _invoice_date(value: Any) -> str:
    """2026-10-30 -> Oct-30th (the format used by the original invoice)."""
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(value or "")

    day = parsed.day
    suffix = "th" if 10 <= day % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return parsed.strftime("%b") + f"-{day}{suffix}"


def _usdate(value: Any) -> str:
    """2025-08-31 -> Aug 31, 2025"""
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").strftime("%b %d, %Y")
    except (TypeError, ValueError):
        return str(value or "")


def _prep_render_data(invoice: Dict[str, Any]) -> Dict[str, Any]:
    """Turn the invoice dict into the context the template expects."""
    items: List[Dict[str, Any]] = []
    for item in invoice.get("items", []):
        qty = item.get("quantity", 0) or 0
        price = item.get("unit-price", 0) or 0
        items.append({
            "description": item.get("description", ""),
            "quantity": qty,
            "unit-price": price,
            "amount": qty * price,
        })

    return {
        # The number typed by the user wins; fall back to the internal id.
        "invoiceNumber": invoice.get("invoice-number") or invoice.get("invoice-id", ""),
        "date": invoice.get("date", ""),
        "issuerName": config.INVOICE_ISSUER_NAME,
        "issuerAddress": config.INVOICE_ISSUER_ADDRESS,
        "clientName": invoice.get("client-name", ""),
        "clientEmail": invoice.get("client-email", ""),
        "clientAddress": invoice.get("client-address", ""),
        "dueDate": invoice.get("due-date", ""),
        "subtotal": invoice.get("subtotal", 0),
        "tax": invoice.get("tax", 0),
        "total": invoice.get("total", 0),
        "bankInfo": invoice.get("bank-info", ""),
        "items": items,
    }


def render_invoice_html(invoice: Dict[str, Any], font_base: str = "../fonts/") -> str:
    """Render the template to HTML.

    Used for both the PDF and the in-browser preview: some browsers refuse to
    display embedded PDFs, while this view always works.
    """
    # autoescape: invoice fields are user input, never trusted HTML.
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["money"] = _money
    env.filters["qty"] = _qty
    env.filters["usdate"] = _usdate
    env.filters["invoicedate"] = _invoice_date
    template = env.get_template(TEMPLATE_FILE)
    return template.render(**{**_prep_render_data(invoice), "font_base": font_base})


def generate_invoice_pdf(invoice: Dict[str, Any]) -> bytes:
    """Render the HTML template and build the PDF in memory (bytes)."""
    from weasyprint import HTML

    return HTML(
        string=render_invoice_html(invoice), base_url=str(TEMPLATE_DIR)
    ).write_pdf()


def save_invoice_pdf(invoice: Dict[str, Any]) -> str:
    """Write the PDF to .tmp/invoices/INV-xxx.pdf and return its path."""
    ensure_tmp_invoices_dir()
    pdf_bytes = generate_invoice_pdf(invoice)
    filename = INVOICES_DIR / f"{invoice['invoice-id']}.pdf"
    filename.write_bytes(pdf_bytes)
    print(f"PDF saved to {filename}")
    return str(filename)