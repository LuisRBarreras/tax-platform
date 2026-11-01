"""Template rendering: formatting filters, escaping and content."""
from app.pdf import (
    _invoice_date,
    _money,
    _qty,
    _prep_render_data,
    _usdate,
    render_invoice_html,
)


def test_money_filter():
    assert _money(1250) == "$1,250.00"
    assert _money(0) == "$0.00"
    assert _money(None) == "$0.00"
    assert _money("not-a-number") == "$0.00"


def test_qty_filter_drops_trailing_zero():
    assert _qty(1.0) == "1"
    assert _qty(2.5) == "2.5"
    assert _qty(None) == "0"


def test_invoice_date_ordinal_suffixes():
    assert _invoice_date("2026-10-30") == "Oct-30th"
    assert _invoice_date("2026-11-01") == "Nov-1st"
    assert _invoice_date("2026-11-02") == "Nov-2nd"
    assert _invoice_date("2026-11-03") == "Nov-3rd"
    assert _invoice_date("2026-11-21") == "Nov-21st"
    assert _invoice_date("2026-11-11") == "Nov-11th"


def test_invoice_date_keeps_bad_input():
    assert _invoice_date("") == ""
    assert _invoice_date("30/10/2026") == "30/10/2026"


def test_usdate_filter():
    assert _usdate("2025-08-31") == "Aug 31, 2025"
    assert _usdate("") == ""


def test_prep_render_data_computes_amounts(sample_invoice):
    context = _prep_render_data(sample_invoice)
    assert context["items"][0]["amount"] == 1000
    assert context["total"] == 1000
    assert context["invoiceNumber"] == "2026-001"


def test_render_contains_client_and_issuer(sample_invoice):
    html = render_invoice_html(sample_invoice)
    assert "Test Client LLC" in html
    assert "Test Issuer" in html
    assert "DESCRIPTION / MEMO" in html


def test_render_uses_invoice_number_over_id(sample_invoice):
    html = render_invoice_html({**sample_invoice, "invoice-number": "2026-042"})
    assert "2026-042" in html


def test_render_falls_back_to_id_when_number_is_empty(sample_invoice):
    html = render_invoice_html({**sample_invoice, "invoice-number": ""})
    assert sample_invoice["invoice-id"] in html


def test_render_escapes_user_html(sample_invoice):
    """A description is data, never markup: this is the XSS regression test."""
    invoice = {
        **sample_invoice,
        "items": [{"description": "<script>alert(1)</script>", "quantity": 1, "unit-price": 1}],
    }
    html = render_invoice_html(invoice)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_does_not_evaluate_jinja_in_data(sample_invoice):
    invoice = {
        **sample_invoice,
        "items": [{"description": "{{ 7*7 }}", "quantity": 1, "unit-price": 1}],
    }
    html = render_invoice_html(invoice)
    assert "{{ 7*7 }}" in html
    assert "49" not in html.replace("2026", "")
