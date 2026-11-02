"""Email building: formatting, recipients, attachments and dry run."""
from email import policy
from email.parser import BytesParser
from pathlib import Path

import pytest

from app import config, emailer
from app.invoice import build_invoice


def test_recipients_are_read_from_config(monkeypatch):
    monkeypatch.setattr(config, "MAIL_RECIPIENTS", " a@x.com , b@y.com ,, ")
    assert emailer.recipients() == ["a@x.com", "b@y.com"]


def test_recipients_empty_by_default(monkeypatch):
    monkeypatch.setattr(config, "MAIL_RECIPIENTS", "")
    assert emailer.recipients() == []


def test_work_period_same_month():
    assert emailer.work_period("2026-10-16", "2026-10-31") == "16 al 31 de Oct"


def test_work_period_across_months():
    assert emailer.work_period("2026-09-28", "2026-10-12") == "28 Sep al 12 de Oct"


def test_work_period_invalid_input():
    assert emailer.work_period("", "") == ""


def test_short_date():
    assert emailer.short_date("2026-10-30") == "30 de Oct"
    assert emailer.short_date("nope") == ""


def test_pesos_prefers_manual_override(sample_invoice):
    assert emailer.pesos({**sample_invoice, "pesos": 19000}) == 19000


def test_pesos_computes_from_rate(sample_invoice):
    assert emailer.pesos({**sample_invoice, "total": 1000, "exchange-rate": 18.5}) == 18500


def test_build_message_default_subject(sample_invoice):
    message = emailer.build_message(sample_invoice, "to@example.com", with_attachments=False)
    assert message["Subject"] == "Invoice 2026-001 — 16 al 31 de Oct"
    assert message["To"] == "to@example.com"


def test_build_message_custom_subject(sample_invoice):
    message = emailer.build_message(
        sample_invoice, "to@example.com", with_attachments=False, subject="Hello"
    )
    assert message["Subject"] == "Hello"


def test_build_message_rejects_header_injection(sample_invoice):
    with pytest.raises(ValueError):
        emailer.build_message(
            sample_invoice, "to@example.com", with_attachments=False,
            subject="Hi\r\nBcc: attacker@example.com",
        )


def test_build_message_has_text_and_html_parts(sample_invoice):
    message = emailer.build_message(sample_invoice, "to@example.com", with_attachments=False)
    types = {part.get_content_type() for part in message.walk()}
    assert "text/plain" in types
    assert "text/html" in types


def test_dry_run_writes_eml(sample_invoice, tmp_dir):
    result = emailer.send_invoice_email(sample_invoice, "to@example.com")

    assert result["dry-run"] is True
    path = Path(result["path"])
    assert path.exists()

    parsed = BytesParser(policy=policy.default).parse(path.open("rb"))
    assert parsed["To"] == "to@example.com"


def test_attachments_include_pdf_and_proof(sample_invoice, tmp_dir):
    pdf = tmp_dir / "INV-test.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    proof = tmp_dir / "INV-test.png"
    proof.write_bytes(b"\x89PNG fake")

    invoice = {
        **sample_invoice,
        "pdf-path": str(pdf),
        "proof-path": str(proof),
    }
    message = emailer.build_message(invoice, "to@example.com")

    names = sorted(a.get_filename() for a in message.iter_attachments())
    # Renamed on the way out, whatever the files are called on disk.
    assert names == ["comprobante-30-oct.png", "invoice-2026-001.pdf"]


def test_no_attachments_when_files_missing(sample_invoice):
    message = emailer.build_message(
        {**sample_invoice, "pdf-path": "/nope.pdf", "proof-path": "/nope.png"},
        "to@example.com",
    )
    assert list(message.iter_attachments()) == []


def test_preview_has_no_binary_attachments(sample_invoice, tmp_dir):
    pdf = tmp_dir / "preview.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    invoice = {**sample_invoice, "pdf-path": str(pdf)}

    preview = emailer.preview(invoice, "to@example.com")

    assert preview["subject"].startswith("Invoice 2026-001")
    assert "Tipo de cambio" in preview["html"]
    assert preview["attachments"] == ["invoice-2026-001.pdf"]  # no proof attached


def test_pdf_name_uses_the_invoice_number():
    assert emailer.pdf_filename({"invoice-number": "49"}) == "invoice-49.pdf"
    assert (
        emailer.pdf_filename({"invoice-number": "2026-010", "invoice-id": "INV-x"})
        == "invoice-2026-010.pdf"
    )


def test_pdf_name_is_safe_for_slashes_and_spaces():
    assert emailer.pdf_filename({"invoice-number": "2026/010 A"}) == "invoice-2026-010-A.pdf"


def test_pdf_name_falls_back_to_the_invoice_id():
    assert emailer.pdf_filename({"invoice-id": "INV-abc"}) == "invoice-INV-abc.pdf"


def test_proof_name_uses_the_deposit_date():
    invoice = {"deposit-date": "2026-11-15"}
    assert emailer.proof_filename(invoice, "/tmp/x.pdf") == "comprobante-15-nov.pdf"
    assert emailer.proof_filename(invoice, "/tmp/x.JPG") == "comprobante-15-nov.jpg"


def test_proof_name_falls_back_to_the_invoice_date():
    invoice = {"date": "2026-01-02"}
    assert emailer.proof_filename(invoice, "/tmp/x.png") == "comprobante-2-ene.png"


def test_proof_name_without_dates_uses_today():
    name = emailer.proof_filename({}, "/tmp/x.jpeg")
    assert name.startswith("comprobante-") and name.endswith(".jpeg")
