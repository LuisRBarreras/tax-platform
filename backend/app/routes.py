"""API routes: they only map URLs to handlers.

A single router with the `/api` prefix; the logic lives in `app.handlers`.
"""
from typing import Any, Dict

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from . import handlers
from .schemas import CreateInvoiceRequest, SendInvoiceRequest

router = APIRouter(prefix="/api")


# -------------------------------- invoices --------------------------------
@router.post("/invoices", tags=["invoices"])
def create_invoice(req: CreateInvoiceRequest) -> Dict[str, Any]:
    return handlers.create_invoice(req)


@router.get("/invoices", tags=["invoices"])
def list_invoices(page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    return handlers.list_invoices(page, per_page)


@router.get("/invoices/{invoice_id}", tags=["invoices"])
def get_invoice(invoice_id: str) -> Dict[str, Any]:
    return handlers.get_invoice(invoice_id)


@router.get("/invoices/{invoice_id}/pdf", tags=["invoices"])
def get_invoice_pdf(invoice_id: str) -> FileResponse:
    return handlers.get_invoice_pdf(invoice_id)


@router.get("/invoices/{invoice_id}/html", response_class=HTMLResponse, tags=["invoices"])
def get_invoice_html(invoice_id: str) -> HTMLResponse:
    return handlers.get_invoice_html(invoice_id)


# ------------------------------ proofs ------------------------------------
@router.post("/invoices/{invoice_id}/upload-proof", tags=["proofs"])
async def upload_proof(invoice_id: str, proof: UploadFile = File(...)) -> Dict[str, Any]:
    return await handlers.upload_proof(invoice_id, proof)


@router.get("/invoices/{invoice_id}/proof", tags=["proofs"])
def get_proof(invoice_id: str) -> FileResponse:
    return handlers.get_proof(invoice_id)


# -------------------------------- email -----------------------------------
@router.get("/mail/recipients", tags=["mail"])
def mail_recipients() -> Dict[str, Any]:
    return handlers.mail_recipients()


@router.get("/invoices/{invoice_id}/email-preview", tags=["mail"])
def email_preview(invoice_id: str, to: str = "", subject: str = "") -> Dict[str, Any]:
    return handlers.email_preview(invoice_id, to, subject)


@router.post("/invoices/{invoice_id}/send", tags=["mail"])
def send_invoice(invoice_id: str, req: SendInvoiceRequest) -> Dict[str, Any]:
    return handlers.send_invoice(invoice_id, req)
