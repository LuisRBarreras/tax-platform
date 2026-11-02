"""Endpoint logic.

The real work lives here (validate, generate, persist, send). Routes only map
URLs to functions in this module.
"""
import os
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from . import config
from . import emailer
from . import invoice as invoice_service
from . import invoice_store as store
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
