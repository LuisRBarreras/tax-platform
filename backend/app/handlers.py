"""Endpoint logic.

The real work lives here (validate, generate, persist, send). Routes only map
URLs to functions in this module.
"""
import os
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Any, Dict

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from . import config
from . import emailer
from . import invoice as invoice_service
from . import invoice_store as store
from . import mailbox
from . import payables_store as payables
from . import pdf as pdf_service
from . import sheets
from .schemas import CreateInvoiceRequest, SendInvoiceRequest

# --------------------------------------------------------------------------
# Invoices
# --------------------------------------------------------------------------


def create_invoice(req: CreateInvoiceRequest) -> Dict[str, Any]:
    invoice = invoice_service.build_invoice(req.to_service_data())

    try:
        # PDF first: if generation fails there is no orphan record.
        pdf_path = pdf_service.save_invoice_pdf(invoice)
        invoice["pdf-path"] = pdf_path
        store.save_invoice(invoice)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"No se pudo crear la factura: {exc}")

    return {
        "success": True,
        "invoice-id": invoice["invoice-id"],
        "message": "Factura creada, PDF generado y guardado en .tmp.",
        "pdf-size": os.path.getsize(pdf_path),
    }


def list_invoices(page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    page = max(1, page)
    per_page = min(max(1, per_page), 100)

    invoices, total = store.get_invoices_page(page, per_page)

    return {
        "invoices": invoices,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, -(-total // per_page)),  # ceil without floats
    }


def get_invoice(invoice_id: str) -> Dict[str, Any]:
    invoice = store.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return invoice


def delete_invoice(invoice_id: str) -> Dict[str, Any]:
    """Remove the invoice, its PDF and its payment proof."""
    invoice = store.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    if not store.delete_invoice(invoice_id):
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    # The row is gone: drop the files so nothing is left pointing at them.
    removed = []
    for key in ("pdf-path", "proof-path"):
        path = invoice.get(key) or ""
        if path and os.path.exists(path):
            try:
                os.remove(path)
                removed.append(os.path.basename(path))
            except OSError:
                pass  # a file we cannot delete must not fail the request

    return {"success": True, "invoice-id": invoice_id, "files-removed": removed}


def get_invoice_pdf(invoice_id: str) -> FileResponse:
    if store.get_invoice(invoice_id) is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    path = os.path.join(config.TMP_INVOICES_DIR, f"{invoice_id}.pdf")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="PDF no encontrado")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{invoice_id}.pdf",
        content_disposition_type="inline",
    )


def get_invoice_html(invoice_id: str) -> HTMLResponse:
    """Preview: the very same HTML used to build the PDF.

    Served separately because some browsers do not render embedded PDFs,
    while plain HTML always shows up.
    """
    invoice = store.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    return HTMLResponse(
        content=pdf_service.render_invoice_html(invoice, font_base="/api/fonts/")
    )


# --------------------------------------------------------------------------
# Payment proof
# --------------------------------------------------------------------------

# Accepted MIME types -> extension used on disk
PROOF_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "application/pdf": ".pdf",
}
MAX_PROOF_BYTES = 10 * 1024 * 1024  # 10 MB


async def upload_proof(invoice_id: str, proof: UploadFile) -> Dict[str, Any]:
    if store.get_invoice(invoice_id) is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    extension = PROOF_TYPES.get(proof.content_type or "")
    if extension is None:
        raise HTTPException(
            status_code=415,
            detail=f"Tipo no soportado: {proof.content_type}. Usa {', '.join(PROOF_TYPES)}",
        )

    # Reject oversized uploads before pulling them into memory.
    if proof.size is not None and proof.size > MAX_PROOF_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Máximo {MAX_PROOF_BYTES // 1024 // 1024} MB"
        )

    data = await proof.read()
    if not data:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if len(data) > MAX_PROOF_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Máximo {MAX_PROOF_BYTES // 1024 // 1024} MB"
        )

    os.makedirs(config.PROOFS_DIR, exist_ok=True)
    path = os.path.join(config.PROOFS_DIR, f"{invoice_id}{extension}")

    # If a proof was uploaded before with another extension, drop the stale file.
    for other in PROOF_TYPES.values():
        stale = os.path.join(config.PROOFS_DIR, f"{invoice_id}{other}")
        if other != extension and os.path.exists(stale):
            os.remove(stale)

    with open(path, "wb") as handle:
        handle.write(data)

    store.set_proof_path(invoice_id, path)

    return {
        "success": True,
        "invoice-id": invoice_id,
        "proof-path": path,
        "size": len(data),
        "content-type": proof.content_type,
    }


def get_proof(invoice_id: str) -> FileResponse:
    invoice = store.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    proof_path = invoice.get("proof-path")
    if not proof_path or not os.path.exists(proof_path):
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")

    return FileResponse(proof_path, filename=os.path.basename(proof_path))


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------


def _allowed_recipient(to: str) -> str:
    """Validate the recipient against the allowlist and return the chosen one."""
    allowed = emailer.recipients()
    if not allowed:
        raise HTTPException(
            status_code=400,
            detail="No hay destinatarios configurados (variable MAIL_RECIPIENTS en backend/.env)",
        )

    recipient = to or allowed[0]
    if recipient not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Destinatario no permitido. Opciones: {', '.join(allowed)}",
        )
    return recipient


def mail_recipients() -> Dict[str, Any]:
    return {"recipients": emailer.recipients(), "dry-run": emailer.is_dry_run()}


def email_preview(invoice_id: str, to: str = "", subject: str = "") -> Dict[str, Any]:
    invoice = store.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    recipient = _allowed_recipient(to)
    return emailer.preview(invoice, recipient, subject=subject or None)


def send_invoice(invoice_id: str, req: SendInvoiceRequest) -> Dict[str, Any]:
    invoice = store.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    recipient = _allowed_recipient(req.to)

    pdf_path = invoice.get("pdf-path")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=409, detail="La factura no tiene PDF generado")

    try:
        result = emailer.send_invoice_email(invoice, recipient, subject=req.subject or None)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo enviar el correo: {exc}")

    sent_at = result.get("sent-at") or datetime.now(timezone.utc).isoformat()
    store.mark_sent(invoice_id, recipient, sent_at)

    # The email is already out: a spreadsheet problem must not fail the request.
    sheet = sheets.record_send(invoice, sent_at=sent_at, recipient=recipient)

    return {"success": True, "invoice-id": invoice_id, **result, "sheet": sheet}


def sheet_info() -> Dict[str, Any]:
    """Where the invoice rows go, so the UI can link to it."""
    try:
        tab = sheets.tab_name()
    except Exception:
        tab = config.GOOGLE_SHEETS_TAB  # misconfigured: still show what is set
    return {
        "url": sheets.sheet_url(),
        "tab": tab,
        "enabled": config.GOOGLE_SHEETS_ENABLED,
    }


# --------------------------------------------------------------------------
# Payables: invoices received by mail that still have to be paid
# --------------------------------------------------------------------------


def _payables_dir(*parts: str) -> str:
    path = os.path.join(config.PAYABLES_DIR, *parts)
    os.makedirs(path, exist_ok=True)
    return path


RECEIPT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf"}


def _save_receipt(data: bytes, extension: str, name: str) -> str:
    path = os.path.join(_payables_dir("receipts"), f"{name}{extension}")
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def list_receipts() -> Dict[str, Any]:
    """Files in RECEIPTS_DIR, newest first, so the UI can offer them as a picker."""
    directory = config.RECEIPTS_DIR
    if not directory or not os.path.isdir(directory):
        return {"receipts": [], "directory": directory, "available": False}

    entries = []
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        extension = os.path.splitext(name)[1].lower()
        if not os.path.isfile(path) or extension not in RECEIPT_EXTENSIONS:
            continue
        stat = os.stat(path)
        entries.append(
            {
                "name": name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            }
        )

    entries.sort(key=lambda item: item["modified"], reverse=True)
    return {"receipts": entries[:60], "directory": directory, "available": True}


async def _store_receipt(proof: UploadFile, name: str) -> tuple[str, int]:
    """Validate and save the receipt the same way invoice proofs are saved."""
    extension = PROOF_TYPES.get(proof.content_type or "")
    if extension is None:
        raise HTTPException(
            status_code=415,
            detail=f"Tipo no soportado: {proof.content_type}. Usa {', '.join(PROOF_TYPES)}",
        )
    if proof.size is not None and proof.size > MAX_PROOF_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Máximo {MAX_PROOF_BYTES // 1024 // 1024} MB"
        )

    data = await proof.read()
    if not data:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if len(data) > MAX_PROOF_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Máximo {MAX_PROOF_BYTES // 1024 // 1024} MB"
        )

    return _save_receipt(data, extension, name), len(data)


def list_payables(status: str = "") -> Dict[str, Any]:
    if status not in ("", "pending", "paid"):
        raise HTTPException(status_code=400, detail="Estado inválido")
    return {
        "payables": payables.list_payables(status),
        "counts": payables.count_by_status(),
        "sender": config.PAYABLES_SENDER,
    }


def sync_payables() -> Dict[str, Any]:
    """Read the mailbox: new invoices are added, answered ones become paid."""
    if not config.PAYABLES_SENDER:
        raise HTTPException(
            status_code=400,
            detail="Falta PAYABLES_SENDER en backend/.env (correo del que llegan las facturas)",
        )

    known = payables.known_message_ids()
    try:
        found = mailbox.scan(known)
        replied = mailbox.replied_message_ids()
    except mailbox.MailboxError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo leer el correo: {exc}")

    added = 0
    for entry in found:
        payable_id = payables.row_id(entry["message-id"])
        pdf_path = xml_path = None
        if entry.get("pdf"):
            pdf_path = os.path.join(_payables_dir(), f"{payable_id}.pdf")
            with open(pdf_path, "wb") as handle:
                handle.write(entry["pdf"])
        if entry.get("xml"):
            xml_path = os.path.join(_payables_dir(), f"{payable_id}.xml")
            with open(xml_path, "wb") as handle:
                handle.write(entry["xml"])

        payables.save_payable(
            {
                "id": payable_id,
                "message_id": entry["message-id"],
                "subject": entry.get("subject", ""),
                "sender": entry.get("sender", ""),
                "received_at": entry.get("received-at", ""),
                "folio": entry.get("folio", ""),
                "total": entry.get("total"),
                "subtotal": entry.get("subtotal"),
                "currency": entry.get("currency") or "MXN",
                "cfdi_fecha": entry.get("cfdi-fecha", ""),
                # The CFDI says which month it covers; the date rule is the fallback.
                "period": entry.get("period")
                or payables.period_for(entry.get("cfdi-fecha") or entry.get("received-at", "")),
                "cfdi_uuid": entry.get("cfdi-uuid", ""),
                "issuer_name": entry.get("issuer-name", ""),
                "issuer_rfc": entry.get("issuer-rfc", ""),
                "pdf_path": pdf_path,
                "xml_path": xml_path,
            }
        )
        added += 1

    marked = _mark_replies(replied)

    return {
        "success": True,
        "new": added,
        "marked-paid": marked,
        "counts": payables.count_by_status(),
    }


def _mark_replies(replied: set) -> int:
    """Invoices whose reply already exists in Sent are considered paid."""
    if not replied:
        return 0

    now = datetime.now(timezone.utc).isoformat()
    marked = 0
    for item in payables.list_payables(limit=500):
        if item["status"] != "paid" and item["message-id"] in replied:
            payables.mark_replied(item["id"], now)
            marked += 1
    return marked


def get_payable_pdf(payable_id: str) -> FileResponse:
    item = payables.get_payable(payable_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    path = item.get("pdf-path") or ""
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Esta factura no tiene PDF adjunto")
    return FileResponse(path, media_type="application/pdf", filename=f"factura-{item['folio'] or 'cfdi'}.pdf")


def get_payable_proof(payable_id: str) -> FileResponse:
    item = payables.get_payable(payable_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    path = item.get("proof-path") or ""
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Todavía no hay comprobante")
    return FileResponse(path, filename=os.path.basename(path))


def _receipt_from_folder(filename: str, name: str) -> tuple[str, int]:
    """Copy one file out of RECEIPTS_DIR (no paths, only a file name)."""
    directory = config.RECEIPTS_DIR
    if not directory or not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail="No hay carpeta de comprobantes configurada")

    safe = os.path.basename(filename)
    extension = os.path.splitext(safe)[1].lower()
    if safe != filename or extension not in RECEIPT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Archivo de comprobante inválido")

    path = os.path.join(directory, safe)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"No se encontró {safe} en la carpeta")

    with open(path, "rb") as handle:
        data = handle.read()
    if len(data) > MAX_PROOF_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Máximo {MAX_PROOF_BYTES // 1024 // 1024} MB"
        )
    return _save_receipt(data, extension, name), len(data)


def preview_payable(payable_id: str, receipt: str = "") -> Dict[str, Any]:
    """The reply exactly as it will go out, so it can be reviewed and edited."""
    item = payables.get_payable(payable_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    if item["status"] == "paid":
        raise HTTPException(status_code=409, detail="Esa factura ya está marcada como pagada")

    text, html_body = emailer.payable_reply_body(item)
    suffix = os.path.splitext(os.path.basename(receipt))[1].lower() or ".jpg"

    return {
        "to": parseaddr(item.get("sender", ""))[1],
        "subject": emailer.payable_reply_subject(item),
        "text": text,
        "html": html_body,
        "attachments": [emailer.receipt_filename(item, suffix)],
    }


def delete_payable(payable_id: str) -> Dict[str, Any]:
    """Hide the invoice and drop its files.

    Soft on purpose: the email still exists in the mailbox, so a row that is
    really gone would be recreated by the next sync.
    """
    item = payables.get_payable(payable_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    payables.set_status(payable_id, "deleted", item.get("paid-at") or "")

    removed = []
    for key in ("pdf-path", "xml-path", "proof-path"):
        path = item.get(key) or ""
        if path and os.path.exists(path):
            try:
                os.remove(path)
                removed.append(os.path.basename(path))
            except OSError:
                pass

    return {"success": True, "id": payable_id, "files-removed": removed}


async def pay_payable(
    payable_id: str, proof: UploadFile | None = None, receipt: str = "", message: str = ""
) -> Dict[str, Any]:
    """Take the receipt (uploaded or from the folder), reply, mark it paid."""
    item = payables.get_payable(payable_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    if item["status"] == "paid":
        raise HTTPException(status_code=409, detail="Esa factura ya está marcada como pagada")

    recipient = parseaddr(item.get("sender", ""))[1]
    if not recipient:
        raise HTTPException(status_code=400, detail="El correo original no tiene remitente")
    if config.PAYABLES_SENDER and recipient.lower() != config.PAYABLES_SENDER.lower():
        raise HTTPException(
            status_code=400,
            detail=f"El remitente ({recipient}) no coincide con PAYABLES_SENDER",
        )

    if proof is not None:
        proof_path, size = await _store_receipt(proof, payable_id)
    elif receipt:
        proof_path, size = _receipt_from_folder(receipt, payable_id)
    else:
        raise HTTPException(status_code=400, detail="Falta el comprobante (archivo o nombre)")

    try:
        result = emailer.send_payable_reply(item, proof_path, recipient, message)
    except Exception as exc:
        os.remove(proof_path)
        raise HTTPException(status_code=502, detail=f"No se pudo enviar la respuesta: {exc}")

    sent_at = result.get("sent-at") or datetime.now(timezone.utc).isoformat()
    payables.set_proof(payable_id, proof_path)
    payables.mark_replied(payable_id, sent_at)

    return {
        "success": True,
        "payable": payables.get_payable(payable_id),
        "proof-size": size,
        **result,
    }
