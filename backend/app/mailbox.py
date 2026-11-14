"""Read the invoices that arrive by mail, over IMAP.

Gmail is searched in the "All" folder so archived mail still shows up, and the
"Sent" folder is read once per sync to know which invoices were already replied:
an email counts as answered when a sent message carries its Message-ID in
`In-Reply-To`. That is server state, not our bookkeeping, so a reply sent from
the webmail also counts.
"""
import email
import imaplib
import re
import ssl
from datetime import timezone
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Set

from . import cfdi, config

# Only invoices: "Factura 3133". "'Pago del cliente 2455' is a different mail.
SUBJECT_RE = re.compile(r"^\s*(?:re\s*:\s*)?factura\s*#?\s*(\d{2,})", re.IGNORECASE)


class MailboxError(RuntimeError):
    """IMAP problem, already phrased for the user."""


def _decode(value: Optional[str]) -> str:
    try:
        return str(make_header(decode_header(value or ""))).strip()
    except Exception:
        return (value or "").strip()


def _iso_date(value: Optional[str]) -> str:
    try:
        parsed = parsedate_to_datetime(value or "")
    except (TypeError, ValueError):
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _pick_folder(connection: imaplib.IMAP4_SSL, flag: str, fallback: str) -> str:
    """Resolve a folder by its IMAP flag so the scan works in any language."""
    typ, lines = connection.list()
    for line in lines or []:
        text = line.decode("utf-8", "replace") if isinstance(line, bytes) else str(line)
        if flag.lower() in text.lower():
            parts = text.split('"')
            if len(parts) >= 2 and parts[-2]:
                return parts[-2]
    return fallback


def connect() -> imaplib.IMAP4_SSL:
    if not config.PAYABLES_SENDER:
        raise MailboxError("Falta PAYABLES_SENDER en backend/.env (correo del que llegan las facturas).")
    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        raise MailboxError("Faltan SMTP_USER / SMTP_PASSWORD: se usan también para IMAP.")

    try:
        connection = imaplib.IMAP4_SSL(
            config.IMAP_HOST, config.IMAP_PORT, ssl_context=ssl.create_default_context()
        )
        connection.login(config.SMTP_USER, config.SMTP_PASSWORD)
    except imaplib.IMAP4.error as exc:
        raise MailboxError(f"IMAP rechazó el acceso: {exc}")
    except OSError as exc:
        raise MailboxError(f"No se pudo conectar a {config.IMAP_HOST}: {exc}")
    return connection


def _attachments(message) -> Dict[str, bytes]:
    """{'pdf': bytes, 'xml': bytes} of the invoice the email carries."""
    found: Dict[str, bytes] = {}
    for part in message.walk():
        name = _decode(part.get_filename()).lower()
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        if name.endswith(".pdf") and "pdf" not in found:
            found["pdf"] = payload
        elif name.endswith(".xml") and "xml" not in found:
            found["xml"] = payload
    return found


def _parse_message(raw: bytes) -> Optional[Dict[str, Any]]:
    message = email.message_from_bytes(raw)
    message_id = (message.get("Message-ID") or "").strip()
    subject = _decode(message.get("Subject"))
    match = SUBJECT_RE.match(subject)
    if not message_id or not match:
        return None

    files = _attachments(message)
    invoice = cfdi.parse(files["xml"]) if files.get("xml") else {}

    return {
        "message-id": message_id,
        "subject": subject,
        "sender": _decode(message.get("From")),
        "received-at": _iso_date(message.get("Date")),
        "folio": (invoice.get("folio") or match.group(1)).strip(),
        "total": invoice.get("total"),
        "subtotal": invoice.get("subtotal"),
        "currency": invoice.get("currency") or "MXN",
        "cfdi-fecha": (invoice.get("cfdi_fecha") or "")[:10],
        "cfdi-uuid": invoice.get("uuid", ""),
        "period": invoice.get("period", ""),
        "description": invoice.get("description", ""),
        "issuer-name": invoice.get("issuer_name", ""),
        "issuer-rfc": invoice.get("issuer_rfc", ""),
        "pdf": files.get("pdf", b""),
        "xml": files.get("xml", b""),
    }


def scan(known_message_ids: Set[str]) -> List[Dict[str, Any]]:
    """Invoices already in the database are not downloaded again."""
    connection = connect()
    try:
        folder = config.PAYABLES_FOLDER or _pick_folder(connection, "\\All", "[Gmail]/All Mail")
        connection.select(f'"{folder}"', readonly=True)
        typ, data = connection.search(None, "FROM", f'"{config.PAYABLES_SENDER}"')
        uids = data[0].split() if data and data[0] else []

        invoices: List[Dict[str, Any]] = []
        for uid in uids:
            typ, header_data = connection.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT)])")
            if typ != "OK" or not header_data or not isinstance(header_data[0], tuple):
                continue
            header = email.message_from_bytes(header_data[0][1])
            message_id = (header.get("Message-ID") or "").strip()
            if not message_id or message_id in known_message_ids:
                continue
            if not SUBJECT_RE.match(_decode(header.get("Subject"))):
                continue

            typ, full = connection.fetch(uid, "(RFC822)")
            if typ != "OK" or not full or not isinstance(full[0], tuple):
                continue
            parsed = _parse_message(full[0][1])
            if parsed:
                invoices.append(parsed)
        return invoices
    finally:
        try:
            connection.logout()
        except Exception:
            pass


def replied_message_ids() -> Set[str]:
    """Message-IDs of the invoices whose reply already exists in Sent."""
    connection = connect()
    try:
        folder = _pick_folder(connection, "\\Sent", "[Gmail]/Sent Mail")
        connection.select(f'"{folder}"', readonly=True)
        typ, data = connection.fetch("1:*", "(BODY.PEEK[HEADER.FIELDS (IN-REPLY-TO)])")
        if typ != "OK":
            return set()

        raw = b"".join(part[1] for part in data if isinstance(part, tuple))
        found = re.findall(rb"In-Reply-To:\s*(<[^>\r\n]+>)", raw)
        return {match.decode("utf-8", "replace").strip() for match in found}
    finally:
        try:
            connection.logout()
        except Exception:
            pass
