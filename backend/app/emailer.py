"""Send the invoice email with the PDF and the payment proof attached."""
import re
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Any, Dict, List

from . import config

MONTHS_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MONTHS_FILE = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


# ------------------------------------------------------------------ format --
def money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def rate(value: Any) -> str:
    try:
        return f"${float(value):,.3f}"
    except (TypeError, ValueError):
        return "—"


def work_period(work_from: str, work_to: str) -> str:
    """'2026-10-16' + '2026-10-31' -> '16 al 31 de Oct' (Spanish month names)."""
    try:
        start = datetime.strptime(work_from, "%Y-%m-%d")
        end = datetime.strptime(work_to, "%Y-%m-%d")
    except (TypeError, ValueError):
        return ""

    if start.month == end.month:
        start_label = str(start.day)
    else:
        start_label = f"{start.day} {MONTHS_ES[start.month - 1]}"
    return f"{start_label} al {end.day} de {MONTHS_ES[end.month - 1]}"


def short_date(value: str) -> str:
    """'2026-10-30' -> '30 de Oct'."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return ""
    return f"{parsed.day} de {MONTHS_ES[parsed.month - 1]}"


def _slug(value: Any) -> str:
    """Filename-safe text: '2026/010' -> '2026-010'."""
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    return text.strip("-._") or "invoice"


def pdf_filename(invoice: Dict[str, Any]) -> str:
    """Attachment name of the PDF: 'invoice-<invoice number>.pdf'."""
    return f"invoice-{_slug(invoice.get('invoice-number') or invoice.get('invoice-id'))}.pdf"


def proof_filename(invoice: Dict[str, Any], path: str) -> str:
    """Attachment name of the proof: 'comprobante-<day>-<month>.<ext>'.

    The date is the deposit date (that is what the proof is about); the invoice
    date and today are the fallbacks when it is missing.
    """
    suffix = Path(path).suffix.lower() or ".bin"
    raw = invoice.get("deposit-date") or invoice.get("date") or ""
    try:
        day = datetime.strptime(str(raw), "%Y-%m-%d")
    except (TypeError, ValueError):
        day = datetime.now()
    return f"comprobante-{day.day}-{MONTHS_FILE[day.month - 1]}{suffix}"


def pesos(invoice: Dict[str, Any]) -> float:
    """Hand-entered MXN amount when present; otherwise total x exchange rate."""
    override = invoice.get("pesos")
    if override is not None:
        try:
            return float(override)
        except (TypeError, ValueError):
            pass

    total = float(invoice.get("total") or 0)
    try:
        return total * float(invoice.get("exchange-rate") or 0)
    except (TypeError, ValueError):
        return 0.0


# -------------------------------------------------------------------- data --
def recipients() -> List[str]:
    """Allowed recipients (the UI select), read from .env or the environment."""
    return [item.strip() for item in config.MAIL_RECIPIENTS.split(",") if item.strip()]


def is_dry_run() -> bool:
    """Dry run: do not send, just write the .eml into .tmp/outbox/."""
    return config.SMTP_DRY_RUN


# ----------------------------------------------------------------- message --
def _rows(invoice: Dict[str, Any]) -> Dict[str, str]:
    return {
        "period": work_period(invoice.get("work-from", ""), invoice.get("work-to", "")),
        "deposit": short_date(invoice.get("deposit-date", "")),
        "salary": money(invoice.get("total")),
        "rate": rate(invoice.get("exchange-rate")),
        "pesos": money(pesos(invoice)),
    }


def build_message(
    invoice: Dict[str, Any],
    to: str,
    with_attachments: bool = True,
    subject: str | None = None,
) -> EmailMessage:
    rows = _rows(invoice)
    meta = getattr(invoice, "get", lambda *_: None)
    has_proof = bool(invoice.get("proof-path"))

    attachments = [pdf_filename(invoice)]
    if has_proof:
        attachments.append(proof_filename(invoice, invoice["proof-path"]))

    if not subject:
        number = invoice.get("invoice-number") or invoice["invoice-id"]
        subject = f"Invoice {number}"
        if rows["period"]:
            subject += f" — {rows['period']}"

    text_body = f"""Buen día Rosy

Aquí envío la información del último invoice:

Datos
""" + "".join(f"- {item}\n" for item in attachments) + f"""
Fecha Trabajo\tFecha Depósito\tSalary\tTipo de cambio\tPesos
{rows['period']}\t{rows['deposit']}\t{rows['salary']}\t{rows['rate']}\t{rows['pesos']}
"""

    html_rows = "".join(
        f"<li>{item} (adjunto)</li>" for item in attachments
    )
    html_body = f"""<html><body style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#111">
<p>Buen día Rosy</p>
<p>Aquí envío la información del último invoice:</p>
<p><strong>Datos</strong></p>
<ul>{html_rows}</ul>
<table cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-size:13px">
  <thead>
    <tr style="background:#f2f2f2">
      <th align="left" style="border:1px solid #ddd">Fecha Trabajo</th>
      <th align="left" style="border:1px solid #ddd">Fecha Depósito</th>
      <th align="right" style="border:1px solid #ddd">Salary</th>
      <th align="right" style="border:1px solid #ddd">Tipo de cambio</th>
      <th align="right" style="border:1px solid #ddd">Pesos</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="border:1px solid #ddd">{rows['period']}</td>
      <td style="border:1px solid #ddd">{rows['deposit']}</td>
      <td align="right" style="border:1px solid #ddd">{rows['salary']}</td>
      <td align="right" style="border:1px solid #ddd">{rows['rate']}</td>
      <td align="right" style="border:1px solid #ddd">{rows['pesos']}</td>
    </tr>
  </tbody>
</table>
</body></html>"""

    message = EmailMessage()
    message["Subject"] = subject
    sender = config.MAIL_FROM or formataddr(
        ("Luis Ramon Barreras Sanchez", config.SMTP_USER or "no-reply@localhost")
    )
    message["From"] = sender
    message["To"] = to
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    if not with_attachments:
        return message

    pdf_path = invoice.get("pdf-path")
    if pdf_path and Path(pdf_path).exists():
        message.add_attachment(
            Path(pdf_path).read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=pdf_filename(invoice),
        )

    if has_proof and Path(invoice["proof-path"]).exists():
        proof = Path(invoice["proof-path"])
        maintype = "application" if proof.suffix.lower() == ".pdf" else "image"
        subtype = "pdf" if proof.suffix.lower() == ".pdf" else proof.suffix.lstrip(".").replace("jpg", "jpeg")
        message.add_attachment(
            proof.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=proof_filename(invoice, str(proof)),
        )

    return message


def send_invoice_email(
    invoice: Dict[str, Any], to: str, subject: str | None = None
) -> Dict[str, Any]:
    """Send the email (or write the .eml when SMTP_DRY_RUN is on)."""
    message = build_message(invoice, to, subject=subject)

    if is_dry_run():
        outbox = Path(config.OUTBOX_DIR)
        outbox.mkdir(parents=True, exist_ok=True)
        path = outbox / f"{invoice['invoice-id']}.eml"
        path.write_bytes(bytes(message))
        return {"dry-run": True, "path": str(path), "to": to, "subject": message["Subject"]}

    if not config.SMTP_HOST or not config.SMTP_USER or not config.SMTP_PASSWORD:
        raise RuntimeError(
            "Falta configuración SMTP (SMTP_HOST / SMTP_USER / SMTP_PASSWORD) "
            "o activa SMTP_DRY_RUN=1"
        )

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(message)

    return {
        "dry-run": False,
        "to": to,
        "subject": message["Subject"],
        "sent-at": datetime.now(timezone.utc).isoformat(),
    }


def preview(invoice: Dict[str, Any], to: str, subject: str | None = None) -> Dict[str, Any]:
    """Return the email exactly as it would be sent, without binary attachments.

    Used by the confirmation screen before sending.
    """
    message = build_message(invoice, to, with_attachments=False, subject=subject)

    html = ""
    text = ""
    for part in message.walk():
        if part.get_content_type() == "text/html":
            html = part.get_content()
        elif part.get_content_type() == "text/plain":
            text = part.get_content()

    attachments = [pdf_filename(invoice)]
    if invoice.get("proof-path"):
        attachments.append(proof_filename(invoice, invoice["proof-path"]))

    return {
        "to": to,
        "subject": message["Subject"],
        "from": message["From"],
        "attachments": attachments,
        "html": html,
        "text": text,
    }
