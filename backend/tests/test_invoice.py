"""Business rules: totals, ids and defaults."""
from app import config
from app.invoice import build_invoice, calculate_totals, generate_invoice_id


def test_generate_invoice_id_format():
    invoice_id = generate_invoice_id()
    assert invoice_id.startswith("INV-")
    assert len(invoice_id) > 20
    assert invoice_id != generate_invoice_id()


def test_calculate_totals_multiplies_quantity_and_price():
    totals = calculate_totals(
        [
            {"quantity": 2, "unit-price": 100},
            {"quantity": 1, "unit-price": 50.5},
        ]
    )
    assert totals == {"subtotal": 250.5, "tax": 0.0, "total": 250.5}


def test_calculate_totals_ignores_missing_values():
    assert calculate_totals([{"quantity": None, "unit-price": None}])["total"] == 0


def test_build_invoice_keeps_requested_date():
    invoice = build_invoice({"date": "2026-10-30", "items": []})
    assert invoice["date"] == "2026-10-30"


def test_build_invoice_falls_back_to_today():
    invoice = build_invoice({"items": []})
    assert len(invoice["date"]) == 10  # YYYY-MM-DD


def test_build_invoice_fills_client_from_config():
    invoice = build_invoice({"items": []})
    assert invoice["client-name"] == config.INVOICE_CLIENT_NAME
    assert invoice["client-email"] == config.INVOICE_CLIENT_EMAIL
    assert invoice["client-address"] == config.INVOICE_CLIENT_ADDRESS


def test_build_invoice_respects_explicit_client():
    invoice = build_invoice(
        {"client-name": "Other Co", "client-email": "x@y.z", "client-address": "Somewhere", "items": []}
    )
    assert invoice["client-name"] == "Other Co"


def test_build_invoice_keeps_pesos_override():
    assert build_invoice({"pesos": 1234.5, "items": []})["pesos"] == 1234.5
    assert build_invoice({"items": []})["pesos"] is None


def test_build_invoice_default_status_and_timestamp():
    invoice = build_invoice({"items": []})
    assert invoice["status"] == "created"
    assert invoice["created-at"].endswith("+00:00")
