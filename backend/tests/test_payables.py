"""Invoices received by mail: CFDI parsing, storage and the reply flow."""
import email
from email.header import decode_header, make_header

import pytest
from fastapi.testclient import TestClient

from app import config, handlers, mailbox, payables_store as store
from app.main import app

CFDI = b"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0"
    Folio="3133" Fecha="2026-11-12T21:48:10" SubTotal="2000.00" Total="2320.00" Moneda="MXN">
  <cfdi:Emisor Rfc="VEAR540818TJ1" Nombre="ROSA MARIA VELEZ ESCALANTE ALLEGRE"/>
  <cfdi:Receptor Rfc="BASL900901H40" Nombre="LUIS RAMON BARRERAS SANCHEZ"/>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
        UUID="6239596A-62D5-4281-AA27-7AC0E10602CF"/>
  </cfdi:Complemento>
</cfdi:Comprobante>
"""

ENTRY = {
    "message-id": "<3133@outlook.com>",
    "subject": "Factura 3133",
    "sender": "Carla Velez <billing@example.com>",
    "received-at": "2026-11-13T19:17:39+00:00",
    "folio": "3133",
    "total": 2320.0,
    "subtotal": 2000.0,
    "currency": "MXN",
    "cfdi-fecha": "2026-11-12",
    "cfdi-uuid": "6239596A-62D5-4281-AA27-7AC0E10602CF",
    "issuer-name": "ROSA MARIA VELEZ ESCALANTE ALLEGRE",
    "issuer-rfc": "VEAR540818TJ1",
    "pdf": b"%PDF-1.4 fake",
    "xml": CFDI,
}


# ------------------------------------------------------------------- cfdi --
def test_cfdi_reads_folio_amounts_and_issuer():
    data = mailbox.cfdi.parse(CFDI)

    assert data["folio"] == "3133"
    assert data["total"] == 2320.0
    assert data["subtotal"] == 2000.0
    assert data["currency"] == "MXN"
    assert data["cfdi_fecha"] == "2026-11-12T21:48:10"
    assert data["uuid"] == "6239596A-62D5-4281-AA27-7AC0E10602CF"
    assert data["issuer_rfc"] == "VEAR540818TJ1"
    assert "VELEZ" in data["issuer_name"]


def test_cfdi_survives_garbage():
    assert mailbox.cfdi.parse(b"<not xml").get("total") is None
    assert mailbox.cfdi.parse(b"<root/>").get("folio") == ""


# ---------------------------------------------------------------- mailbox --
def _raw_message(subject="Factura 3133", message_id="<3133@outlook.com>"):
    message = email.message.EmailMessage()
    message["Subject"] = subject
    message["Message-ID"] = message_id
    message["From"] = "Carla Velez <billing@example.com>"
    message["Date"] = "Fri, 13 Nov 2026 12:17:39 -0700"
    message.set_content("hola")
    message.add_attachment(CFDI, maintype="text", subtype="xml", filename="F0000003133.xml")
    message.add_attachment(b"%PDF-1.4 fake", maintype="application", subtype="pdf",
                           filename="F0000003133.pdf")
    return bytes(message)


def test_message_is_parsed_with_its_invoice():
    entry = mailbox._parse_message(_raw_message())

    assert entry["folio"] == "3133"
    assert entry["total"] == 2320.0
    assert entry["pdf"].startswith(b"%PDF")
    assert entry["xml"] == CFDI
    assert entry["received-at"].startswith("2026-11-13")


def test_other_subjects_are_ignored():
    assert mailbox._parse_message(_raw_message(subject="Pago del cliente 2455")) is None


def test_subject_regex():
    assert mailbox.SUBJECT_RE.match("Factura 3133")
    assert mailbox.SUBJECT_RE.match("FACTURA 99")
    assert mailbox.SUBJECT_RE.match("Re: Factura 3133")
    assert not mailbox.SUBJECT_RE.match("Pago del cliente 2455")


# ------------------------------------------------------------------ store --
def test_store_roundtrip(clean_db):
    payable_id = store.row_id(ENTRY["message-id"])
    store.save_payable(
        {
            "id": payable_id,
            "message_id": ENTRY["message-id"],
            "subject": ENTRY["subject"],
            "sender": ENTRY["sender"],
            "received_at": ENTRY["received-at"],
            "folio": ENTRY["folio"],
            "total": ENTRY["total"],
            "currency": "MXN",
            "status": "pending",
        }
    )

    saved = store.get_payable(payable_id)
    assert saved is not None
    assert saved["folio"] == "3133"
    assert saved["status"] == "pending"
    assert store.count_by_status() == {"pending": 1}


def test_sync_does_not_revive_a_paid_invoice(clean_db):
    payable_id = store.row_id(ENTRY["message-id"])
    store.save_payable({"id": payable_id, "message_id": ENTRY["message-id"], "folio": "3133"})
    store.mark_replied(payable_id, "2026-11-14T10:00:00+00:00")

    # A later sync re-sends the same email: the status must stay paid.
    store.save_payable({"id": payable_id, "message_id": ENTRY["message-id"], "folio": "3133"})

    assert store.get_payable(payable_id)["status"] == "paid"


def test_pending_comes_before_paid(clean_db):
    store.save_payable({"id": "HON-a", "message_id": "<a@x>", "folio": "1", "received_at": "2026-01-01"})
    store.save_payable({"id": "HON-b", "message_id": "<b@x>", "folio": "2", "received_at": "2026-05-01"})
    store.mark_replied("HON-b", "2026-06-01T00:00:00+00:00")

    assert [item["folio"] for item in store.list_payables()] == ["1", "2"]


# -------------------------------------------------------------------- api --
@pytest.fixture()
def client(clean_db):
    return TestClient(app)


@pytest.fixture()
def mailbox_online(monkeypatch):
    monkeypatch.setattr(
        mailbox, "scan", lambda known: [] if ENTRY["message-id"] in known else [ENTRY]
    )
    monkeypatch.setattr(mailbox, "replied_message_ids", lambda: set())


def test_sync_adds_the_invoice_and_its_files(client, mailbox_online):
    body = client.post("/api/payables/sync").json()

    assert body["new"] == 1
    listed = client.get("/api/payables").json()
    assert [item["folio"] for item in listed["payables"]] == ["3133"]

    payable = listed["payables"][0]
    pdf = client.get(f"/api/payables/{payable['id']}/pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_sync_marks_already_answered_invoices_paid(client, monkeypatch):
    monkeypatch.setattr(
        mailbox, "scan", lambda known: [] if ENTRY["message-id"] in known else [ENTRY]
    )
    monkeypatch.setattr(mailbox, "replied_message_ids", lambda: {ENTRY["message-id"]})

    body = client.post("/api/payables/sync").json()

    assert body["marked-paid"] == 1
    assert client.get("/api/payables").json()["payables"][0]["status"] == "paid"


def test_pay_sends_the_reply_and_marks_it_paid(client, mailbox_online, tmp_dir):
    client.post("/api/payables/sync")
    payable_id = client.get("/api/payables").json()["payables"][0]["id"]
    receipt = tmp_dir / "pago.png"
    receipt.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)

    with receipt.open("rb") as handle:
        response = client.post(
            f"/api/payables/{payable_id}/pay",
            files={"proof": ("pago.png", handle, "image/png")},
        )

    body = response.json()
    assert response.status_code == 200, body
    assert body["payable"]["status"] == "paid"
    assert body["dry-run"] is True  # SMTP_DRY_RUN=1 in tests

    # The .eml is threaded and carries the receipt.
    import pathlib

    eml = pathlib.Path(body["path"]).read_bytes()
    assert b"In-Reply-To: <3133@outlook.com>" in eml
    assert b"comprobante-3133-12-nov.png" in eml


def test_pay_rejects_unknown_and_already_paid(client, mailbox_online, tmp_dir):
    receipt = tmp_dir / "pago.png"
    receipt.write_bytes(b"\x89PNG\r\n\x1a\n")

    assert client.post(
        "/api/payables/HON-nope/pay", files={"proof": ("p.png", b"\x89PNG", "image/png")}
    ).status_code == 404

    client.post("/api/payables/sync")
    payable_id = client.get("/api/payables").json()["payables"][0]["id"]
    files = {"proof": ("pago.png", receipt.read_bytes(), "image/png")}
    assert client.post(f"/api/payables/{payable_id}/pay", files=files).status_code == 200
    assert client.post(f"/api/payables/{payable_id}/pay", files=files).status_code == 409


def test_pay_rejects_a_foreign_sender(client, monkeypatch):
    entry = {**ENTRY, "sender": "Otro <otro@example.com>"}
    monkeypatch.setattr(mailbox, "scan", lambda known: [entry])
    monkeypatch.setattr(mailbox, "replied_message_ids", lambda: set())
    client.post("/api/payables/sync")
    payable_id = client.get("/api/payables").json()["payables"][0]["id"]

    response = client.post(
        f"/api/payables/{payable_id}/pay",
        files={"proof": ("p.png", b"\x89PNG", "image/png")},
    )

    assert response.status_code == 400
    assert "PAYABLES_SENDER" in response.json()["detail"]


def test_invalid_status_filter(client):
    assert client.get("/api/payables?status=whatever").status_code == 400


# ---------------------------------------------------------------- receipts --
def test_receipts_come_from_the_mounted_folder(client, monkeypatch, tmp_dir):
    folder = tmp_dir / "receipts"
    folder.mkdir(exist_ok=True)
    (folder / "octubre.jpeg").write_bytes(b"\xff\xd8\xff" + b"0" * 32)
    (folder / "nota.txt").write_text("ignorado")
    monkeypatch.setattr(config, "RECEIPTS_DIR", str(folder))

    body = client.get("/api/payables/receipts").json()

    assert body["available"] is True
    assert [item["name"] for item in body["receipts"]] == ["octubre.jpeg"]


def test_receipts_report_a_missing_folder(client, monkeypatch):
    monkeypatch.setattr(config, "RECEIPTS_DIR", "/nope/receipts")

    body = client.get("/api/payables/receipts").json()

    assert body == {"receipts": [], "directory": "/nope/receipts", "available": False}


def test_pay_accepts_a_file_from_the_folder(client, mailbox_online, monkeypatch, tmp_dir):
    folder = tmp_dir / "receipts"
    folder.mkdir(exist_ok=True)
    (folder / "octubre.jpeg").write_bytes(b"\xff\xd8\xff" + b"0" * 32)
    monkeypatch.setattr(config, "RECEIPTS_DIR", str(folder))

    client.post("/api/payables/sync")
    payable_id = client.get("/api/payables").json()["payables"][0]["id"]

    response = client.post(
        f"/api/payables/{payable_id}/pay", data={"receipt": "octubre.jpeg"}
    )

    body = response.json()
    assert response.status_code == 200, body
    assert body["payable"]["status"] == "paid"
    assert body["proof-size"] > 0


def test_pay_refuses_a_path_in_the_receipt_name(client, mailbox_online, monkeypatch, tmp_dir):
    monkeypatch.setattr(config, "RECEIPTS_DIR", str(tmp_dir))
    client.post("/api/payables/sync")
    payable_id = client.get("/api/payables").json()["payables"][0]["id"]

    response = client.post(
        f"/api/payables/{payable_id}/pay", data={"receipt": "../secret.jpeg"}
    )

    assert response.status_code == 400


def test_pay_without_a_receipt_is_rejected(client, mailbox_online):
    client.post("/api/payables/sync")
    payable_id = client.get("/api/payables").json()["payables"][0]["id"]

    assert client.post(f"/api/payables/{payable_id}/pay").status_code == 400


# ------------------------------------------------------------------ delete --
def test_delete_hides_the_invoice_and_drops_its_files(client, mailbox_online):
    client.post("/api/payables/sync")
    payable = client.get("/api/payables").json()["payables"][0]
    import pathlib

    pdf = pathlib.Path(payable["pdf-path"])
    assert pdf.exists()

    assert client.delete(f"/api/payables/{payable['id']}").status_code == 200
    assert client.get("/api/payables").json()["payables"] == []
    assert not pdf.exists()


def test_deleted_invoice_does_not_come_back_on_sync(client, mailbox_online):
    client.post("/api/payables/sync")
    payable_id = client.get("/api/payables").json()["payables"][0]["id"]
    client.delete(f"/api/payables/{payable_id}")

    body = client.post("/api/payables/sync").json()

    assert body["new"] == 0
    assert client.get("/api/payables").json()["payables"] == []


def test_delete_unknown_is_404(client):
    assert client.delete("/api/payables/HON-nope").status_code == 404


def test_preview_shows_the_reply_before_sending(client, mailbox_online):
    client.post("/api/payables/sync")
    payable_id = client.get("/api/payables").json()["payables"][0]["id"]

    body = client.get(f"/api/payables/{payable_id}/preview?receipt=octubre.jpeg").json()

    assert body["to"] == "billing@example.com"
    assert body["subject"] == "Re: Factura 3133"
    assert body["attachments"] == ["comprobante-3133-12-nov.jpeg"]
    assert "2,320.00" in body["text"]
    assert "<p>" in body["html"]


def test_a_custom_message_replaces_the_default_one(client, mailbox_online, tmp_dir):
    receipt = tmp_dir / "pago.png"
    receipt.write_bytes(b"\x89PNG\r\n\x1a\n")
    client.post("/api/payables/sync")
    payable_id = client.get("/api/payables").json()["payables"][0]["id"]

    response = client.post(
        f"/api/payables/{payable_id}/pay",
        files={"proof": ("pago.png", receipt.read_bytes(), "image/png")},
        data={"message": "Listo, ya quedó el pago de noviembre. Gracias!"},
    )

    import pathlib

    eml = pathlib.Path(response.json()["path"]).read_bytes()
    assert b"ya qued\xc3\xb3 el pago de noviembre" in eml


def test_preview_of_a_paid_invoice_is_rejected(client, mailbox_online, tmp_dir):
    receipt = tmp_dir / "pago.png"
    receipt.write_bytes(b"\x89PNG\r\n\x1a\n")
    client.post("/api/payables/sync")
    payable_id = client.get("/api/payables").json()["payables"][0]["id"]
    client.post(
        f"/api/payables/{payable_id}/pay",
        files={"proof": ("pago.png", receipt.read_bytes(), "image/png")},
    )

    assert client.get(f"/api/payables/{payable_id}/preview").status_code == 409


# ------------------------------------------------------------------ period --
def test_period_is_the_month_before_the_invoice():
    """3133 dated Nov 12 covers October's honorarios."""
    assert store.period_for("2026-11-12") == "2026-10"
    assert store.period_for("2026-01-09") == "2025-12"  # January wraps into last year
    assert store.period_for("2026-03-04") == "2026-02"
    assert store.period_for("") == ""


def test_sync_stores_the_period(client, mailbox_online):
    client.post("/api/payables/sync")

    payable = client.get("/api/payables").json()["payables"][0]
    assert payable["period"] == "2026-10"


# ------------------------------------------------------ period from the CFDI --
def test_period_comes_from_the_invoice_description():
    """The CFDI says which month it covers; do not guess from the date."""
    from app.cfdi import period_from_text

    assert period_from_text(
        "Honorarios ... correspondientes al periodo de Octubre del 2026."
    ) == "2026-10"
    assert period_from_text(
        "Honorarios ... correspondientes al mes de Marzo de 2025"
    ) == "2025-03"
    assert period_from_text("Acotacion de honorarios") == ""


def test_cfdi_parse_exposes_the_period_and_description():
    xml = CFDI.replace(
        b"<cfdi:Emisor",
        b'<cfdi:Concepto Descripcion="Honorarios correspondientes al periodo de '
        b'Octubre del 2026."/><cfdi:Emisor',
    )

    data = mailbox.cfdi.parse(xml)

    assert data["period"] == "2026-10"
    assert "Octubre del 2026" in data["description"]


def test_a_description_without_a_month_falls_back_to_the_date_rule(clean_db):
    payable_id = store.row_id("<sin-periodo@x>")
    store.save_payable(
        {
            "id": payable_id,
            "message_id": "<sin-periodo@x>",
            "folio": "9999",
            "cfdi_fecha": "2026-11-12",
            "period": "",
        }
    )

    assert store.get_payable(payable_id)["period"] == "2026-10"


def test_sheet_info_points_at_the_configured_tab(client, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_SHEETS_TAB", "2026")
    monkeypatch.setattr(config, "GOOGLE_SHEETS_GID", "")
    monkeypatch.setattr(config, "GOOGLE_SHEETS_ENABLED", True)

    body = client.get("/api/sheets").json()

    assert body["tab"] == "2026"
    assert body["enabled"] is True
    assert body["url"].startswith("https://docs.google.com/spreadsheets/d/")
