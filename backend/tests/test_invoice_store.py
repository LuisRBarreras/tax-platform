"""SQLite persistence: save, read, pagination, state changes."""
from app import invoice_store as store
from app.invoice import build_invoice


def _make(number: str, date: str = "2026-10-30") -> dict:
    return build_invoice(
        {
            "invoice-number": number,
            "date": date,
            "items": [{"description": "Software Service", "quantity": 1, "unit-price": 100}],
        }
    )


def test_save_and_get_roundtrip(clean_db):
    invoice = _make("A-1")
    store.save_invoice(invoice)

    loaded = store.get_invoice(invoice["invoice-id"])
    assert loaded["invoice-number"] == "A-1"
    assert loaded["total"] == 100
    assert loaded["items"][0]["description"] == "Software Service"
    assert "_id" not in loaded


def test_get_invalid_or_unknown_id_returns_none(clean_db):
    assert store.get_invoice("not-an-invoice") is None
    assert store.get_invoice("../../etc/passwd") is None
    assert store.get_invoice("INV-does-not-exist") is None


def test_save_is_upsert(clean_db):
    invoice = _make("A-2")
    store.save_invoice(invoice)
    store.save_invoice({**invoice, "status": "sent"})

    assert len(store.get_all_invoices()) == 1
    assert store.get_invoice(invoice["invoice-id"])["status"] == "sent"


def test_list_is_newest_created_first(clean_db):
    first = _make("A-3")
    store.save_invoice(first)
    second = _make("A-4")
    second["created-at"] = "2999-01-01T00:00:00+00:00"
    store.save_invoice(second)

    numbers = [i["invoice-number"] for i in store.get_all_invoices()]
    assert numbers == ["A-4", "A-3"]


def test_pagination(clean_db):
    for n in range(7):
        store.save_invoice({**_make(f"P-{n}"), "created-at": f"2026-10-0{n + 1}T00:00:00+00:00"})

    page1, total = store.get_invoices_page(page=1, per_page=3)
    page3, _ = store.get_invoices_page(page=3, per_page=3)

    assert total == 7
    assert len(page1) == 3
    assert len(page3) == 1
    assert page1[0]["invoice-number"] == "P-6"  # newest first


def test_mark_sent_updates_status(clean_db):
    invoice = _make("A-5")
    store.save_invoice(invoice)

    store.mark_sent(invoice["invoice-id"], "to@example.com", "2026-11-01T10:00:00+00:00")

    loaded = store.get_invoice(invoice["invoice-id"])
    assert loaded["status"] == "sent"
    assert loaded["sent-to"] == "to@example.com"


def test_proof_and_pdf_paths(clean_db):
    invoice = _make("A-6")
    store.save_invoice(invoice)

    store.set_proof_path(invoice["invoice-id"], ".tmp/proofs/A-6.png")
    assert store.get_invoice(invoice["invoice-id"])["proof-path"] == ".tmp/proofs/A-6.png"

    store.set_proof_path(invoice["invoice-id"], None)
    assert store.get_invoice(invoice["invoice-id"])["proof-path"] is None


def test_delete(clean_db):
    invoice = _make("A-7")
    store.save_invoice(invoice)

    assert store.delete_invoice(invoice["invoice-id"]) is True
    assert store.get_invoice(invoice["invoice-id"]) is None
    assert store.delete_invoice(invoice["invoice-id"]) is False
