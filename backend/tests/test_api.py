"""API contract tests through the ASGI app (no network, dry-run email)."""
import io

import pytest
from fastapi.testclient import TestClient

from app import config, invoice_store as store
from app.main import app


@pytest.fixture()
def client(clean_db):
    return TestClient(app)


def _payload(**overrides):
    base = {
        "invoice-number": "API-1",
        "date": "2026-10-30",
        "work-from": "2026-10-16",
        "work-to": "2026-10-31",
        "deposit-date": "2026-10-30",
        "exchange-rate": 18.5,
        "items": [{"description": "Software Service", "quantity": 1, "unit-price": 1000}],
    }
    base.update(overrides)
    return base


def test_create_invoice_returns_id_and_size(client):
    response = client.post("/api/invoices", json=_payload())
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["invoice-id"].startswith("INV-")
    assert body["pdf-size"] > 0


def test_list_is_paginated(client):
    for n in range(3):
        client.post("/api/invoices", json=_payload(**{"invoice-number": f"API-{n}"}))

    body = client.get("/api/invoices?page=1&per_page=2").json()

    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["invoices"]) == 2


def test_get_unknown_invoice_returns_404_spanish(client):
    response = client.get("/api/invoices/INV-nope")
    assert response.status_code == 404
    assert response.json()["detail"] == "Factura no encontrada"


def test_get_rejects_path_traversal(client):
    assert client.get("/api/invoices/..%2F..%2Fetc%2Fpasswd/pdf").status_code == 404


def test_pdf_and_html_are_served(client):
    invoice_id = client.post("/api/invoices", json=_payload()).json()["invoice-id"]

    pdf = client.get(f"/api/invoices/{invoice_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"

    html = client.get(f"/api/invoices/{invoice_id}/html")
    assert html.status_code == 200
    assert "DESCRIPTION / MEMO" in html.text


def test_security_headers(client):
    response = client.get("/api/invoices")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_upload_proof_happy_path(client):
    invoice_id = client.post("/api/invoices", json=_payload()).json()["invoice-id"]
    files = {"proof": ("proof.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png")}

    response = client.post(f"/api/invoices/{invoice_id}/upload-proof", files=files)
    body = response.json()

    assert response.status_code == 200
    assert body["size"] > 0
    assert store.get_invoice(invoice_id)["proof-path"].endswith(".png")


def test_upload_proof_rejects_unknown_type(client):
    invoice_id = client.post("/api/invoices", json=_payload()).json()["invoice-id"]
    files = {"proof": ("x.txt", io.BytesIO(b"hi"), "text/plain")}

    response = client.post(f"/api/invoices/{invoice_id}/upload-proof", files=files)
    assert response.status_code == 415


def test_upload_proof_rejects_empty_file(client):
    invoice_id = client.post("/api/invoices", json=_payload()).json()["invoice-id"]
    files = {"proof": ("empty.png", io.BytesIO(b""), "image/png")}

    response = client.post(f"/api/invoices/{invoice_id}/upload-proof", files=files)
    assert response.status_code == 400


def test_upload_proof_rejects_oversized_file(client, monkeypatch):
    invoice_id = client.post("/api/invoices", json=_payload()).json()["invoice-id"]
    monkeypatch.setattr("app.handlers.MAX_PROOF_BYTES", 10)
    files = {"proof": ("big.png", io.BytesIO(b"x" * 50), "image/png")}

    response = client.post(f"/api/invoices/{invoice_id}/upload-proof", files=files)
    assert response.status_code == 413


def test_proof_404_when_missing(client):
    invoice_id = client.post("/api/invoices", json=_payload()).json()["invoice-id"]
    response = client.get(f"/api/invoices/{invoice_id}/proof")
    assert response.status_code == 404
    assert response.json()["detail"] == "Comprobante no encontrado"


def test_mail_recipients(client):
    body = client.get("/api/mail/recipients").json()
    assert body["recipients"] == ["billing@example.com", "other@example.com"]
    assert body["dry-run"] is True


def test_email_preview(client):
    invoice_id = client.post("/api/invoices", json=_payload()).json()["invoice-id"]

    response = client.get(f"/api/invoices/{invoice_id}/email-preview?to=billing@example.com")
    body = response.json()

    assert response.status_code == 200
    assert "Tipo de cambio" in body["html"]
    assert body["subject"].startswith("Invoice API-1")


def test_email_preview_rejects_foreign_recipient(client):
    invoice_id = client.post("/api/invoices", json=_payload()).json()["invoice-id"]
    response = client.get(f"/api/invoices/{invoice_id}/email-preview?to=evil@example.com")
    assert response.status_code == 400


def test_send_in_dry_run_marks_invoice_sent(client, tmp_dir):
    invoice_id = client.post("/api/invoices", json=_payload()).json()["invoice-id"]

    response = client.post(
        f"/api/invoices/{invoice_id}/send", json={"to": "billing@example.com"}
    )
    body = response.json()

    assert response.status_code == 200
    assert body["dry-run"] is True
    # No dry run and no disabled sync may ever append a row.
    assert body["sheet"]["status"] in {"skipped", "disabled"}

    stored = store.get_invoice(invoice_id)
    assert stored["status"] == "sent"
    assert stored["sent-to"] == "billing@example.com"


def test_send_rejects_foreign_recipient(client):
    invoice_id = client.post("/api/invoices", json=_payload()).json()["invoice-id"]
    response = client.post(f"/api/invoices/{invoice_id}/send", json={"to": "evil@example.com"})

    assert response.status_code == 400
    assert "no permitido" in response.json()["detail"].lower()


def test_no_recipients_configured(client, monkeypatch):
    monkeypatch.setattr(config, "MAIL_RECIPIENTS", "")
    invoice_id = client.post("/api/invoices", json=_payload()).json()["invoice-id"]

    response = client.post(f"/api/invoices/{invoice_id}/send", json={})
    assert response.status_code == 400
    assert "MAIL_RECIPIENTS" in response.json()["detail"]
