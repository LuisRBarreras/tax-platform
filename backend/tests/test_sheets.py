"""Spreadsheet append: payload shape, column mapping and failure handling.

Nothing here touches the network: `_authorized` is replaced by a fake session.
"""
import json

import pytest

from app import config, sheets

HEADERS = [
    "Fecha Trabajo",
    "Fecha Depósito",
    "Salary",
    "Tipo de cambio",
    "Pesos",
    "Invoice",
    "Factura enviada",
    "Comentarios",
]


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


class FakeSession:
    """Minimal stand-in for google.auth's AuthorizedSession."""

    def __init__(self, header_row=None, append_status=200):
        self.header_row = HEADERS if header_row is None else header_row
        self.append_status = append_status
        self.gets = []
        self.posts = []

    def get(self, url, params=None, timeout=None):
        self.gets.append({"url": url, "params": params})
        if not self.header_row:
            return FakeResponse(200, {})
        return FakeResponse(200, {"values": [list(self.header_row)]})

    def post(self, url, params=None, json=None, timeout=None):  # noqa: A002
        self.posts.append({"url": url, "params": params, "json": json})
        if self.append_status != 200:
            return FakeResponse(
                self.append_status,
                {
                    "error": {
                        "code": self.append_status,
                        "message": "The caller does not have permission",
                        "details": [{"reason": "PERMISSION_DENIED"}],
                    }
                },
            )
        return FakeResponse(200, {"updates": {"updatedRange": "'Copy of 2026'!A58:J58"}})


@pytest.fixture()
def fake(monkeypatch, settings):
    """Fresh module state plus a fake session authorised 'for free'."""
    session = FakeSession()
    monkeypatch.setattr(sheets, "_session", None, raising=False)
    monkeypatch.setattr(sheets, "_headers", None, raising=False)
    monkeypatch.setattr(sheets, "_authorized", lambda: session)
    monkeypatch.setattr(settings, "GOOGLE_SPREADSHEET_ID", "sheet-id")
    monkeypatch.setattr(settings, "GOOGLE_SHEETS_TAB", "Copy of 2026")
    monkeypatch.setattr(settings, "GOOGLE_SHEETS_ENABLED", True)
    return session


def test_row_follows_the_header_order(sample_invoice, fake):
    row = sheets.build_row(sample_invoice, "2026-10-31T10:00:00+00:00")

    assert row == [
        "16 al 31 de Oct",
        "30 de Oct",
        1000.0,
        18.5,
        18500.0,
        "2026-001",
        "Si",
        "",
    ]


def test_unknown_headers_stay_empty(sample_invoice, fake):
    only_what_we_use = ["Salary", "Algo raro", "Pesos"]
    row = sheets.build_row(sample_invoice, header_row=only_what_we_use)

    assert row == [1000.0, "", 18500.0]


def test_headers_without_accents_or_case_still_match(sample_invoice, fake):
    row = sheets.build_row(sample_invoice, header_row=["FECHA DE DEPOSITO", "tipo  cambio"])

    assert row == ["30 de Oct", 18.5]


def test_empty_tab_uses_the_default_columns(sample_invoice, monkeypatch, settings):
    fake = FakeSession(header_row=[])
    monkeypatch.setattr(sheets, "_session", None, raising=False)
    monkeypatch.setattr(sheets, "_headers", None, raising=False)
    monkeypatch.setattr(sheets, "_authorized", lambda: fake)
    monkeypatch.setattr(settings, "GOOGLE_SHEETS_TAB", "Copy of 2026")

    row = sheets.build_row(sample_invoice)

    assert row == ["16 al 31 de Oct", "30 de Oct", 1000.0, 18.5, 18500.0]


def test_append_posts_to_the_tab_and_inserts_rows(sample_invoice, fake):
    result = sheets.append_row(sample_invoice, "2026-10-31T10:00:00+00:00")

    assert result["status"] == "appended"
    assert result["range"] == "'Copy of 2026'!A58:J58"
    assert result["url"].startswith("https://docs.google.com/spreadsheets/d/sheet-id")

    assert len(fake.posts) == 1
    post = fake.posts[0]
    assert "sheet-id/values/" in post["url"]
    assert post["url"].endswith(":append")
    assert "Copy%20of%202026" in post["url"]
    assert post["params"] == {
        "valueInputOption": "USER_ENTERED",
        "insertDataOption": "INSERT_ROWS",
    }
    # Trailing blanks are trimmed: never write into the summary columns.
    assert post["json"]["values"] == [
        ["16 al 31 de Oct", "30 de Oct", 1000.0, 18.5, 18500.0, "2026-001", "Si"]
    ]


def test_summary_columns_to_the_right_are_not_written(sample_invoice, monkeypatch, settings):
    """The real tab has a totals block in I1:M1: it must not widen the row."""
    monkeypatch.setattr(sheets, "_session", None, raising=False)
    monkeypatch.setattr(sheets, "_headers", None, raising=False)
    monkeypatch.setattr(settings, "GOOGLE_SHEETS_TAB", "Copy of 2026")
    fake = FakeSession(
        header_row=["Invoice", "Fecha Trabajo", "Pesos", "Total", 445088.75, "Promedio", 63584.1]
    )
    monkeypatch.setattr(sheets, "_authorized", lambda: fake)

    sheets.append_row(sample_invoice, "2026-10-31T10:00:00+00:00")

    assert fake.posts[0]["json"]["values"] == [["2026-001", "16 al 31 de Oct", 18500.0]]


def test_headers_are_read_once_per_process(sample_invoice, fake):
    sheets.append_row(sample_invoice)
    sheets.append_row(sample_invoice)

    assert len(fake.gets) == 1
    assert len(fake.posts) == 2


def test_record_send_is_skipped_in_dry_run(sample_invoice, fake, monkeypatch):
    monkeypatch.setattr(sheets.emailer, "is_dry_run", lambda: True)

    result = sheets.record_send(sample_invoice)

    assert result["status"] == "skipped"
    assert fake.posts == []


def test_record_send_is_skipped_when_disabled(sample_invoice, fake, settings, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_SHEETS_ENABLED", False)
    monkeypatch.setattr(sheets.emailer, "is_dry_run", lambda: False)

    assert sheets.record_send(sample_invoice)["status"] == "disabled"
    assert fake.posts == []


def test_permission_error_is_reported_not_raised(sample_invoice, fake, monkeypatch):
    fake.append_status = 403
    monkeypatch.setattr(sheets.emailer, "is_dry_run", lambda: False)

    result = sheets.record_send(sample_invoice)

    assert result["status"] == "error"
    assert "permiso" in result["message"].lower()


def test_disabled_api_message_points_to_the_console(monkeypatch, settings):
    response = FakeResponse(
        403,
        {
            "error": {
                "code": 403,
                "message": "Google Sheets API has not been used in project 1",
                "details": [{"reason": "SERVICE_DISABLED"}],
            },
        },
    )

    message = sheets._explain(response)

    assert "deshabilitada" in message.lower()


def test_missing_spreadsheet_id_says_which_variable(monkeypatch, settings):
    monkeypatch.setattr(settings, "GOOGLE_SPREADSHEET_ID", "")

    with pytest.raises(sheets.SheetError) as error:
        sheets.spreadsheet_id()

    assert "GOOGLE_SPREADSHEET_ID" in str(error.value)


def test_gid_and_name_must_agree(monkeypatch, settings):
    """The URL gid is authoritative: a name that points elsewhere is an error."""
    monkeypatch.setattr(sheets, "tabs", lambda: {1997921848: "2026"})
    monkeypatch.setattr(settings, "GOOGLE_SHEETS_GID", "1997921848")
    monkeypatch.setattr(settings, "GOOGLE_SHEETS_TAB", "Copy of 2026")

    with pytest.raises(sheets.SheetError) as error:
        sheets.tab_name()

    assert "Copy of 2026" in str(error.value)
    assert "2026" in str(error.value)


def test_gid_wins_when_the_name_is_empty(monkeypatch, settings):
    monkeypatch.setattr(sheets, "tabs", lambda: {1859673291: "Copy of 2026"})
    monkeypatch.setattr(settings, "GOOGLE_SHEETS_GID", "1859673291")
    monkeypatch.setattr(settings, "GOOGLE_SHEETS_TAB", "")

    assert sheets.tab_name() == "Copy of 2026"


def test_header_row_stops_at_the_totals_block(sample_invoice, monkeypatch, settings):
    """Numbers to the right of the table are a summary, not columns."""
    monkeypatch.setattr(sheets, "_session", None, raising=False)
    monkeypatch.setattr(sheets, "_headers", None, raising=False)
    monkeypatch.setattr(settings, "GOOGLE_SHEETS_GID", "")
    fake = FakeSession(
        header_row=["Invoice", "Salary", "Total", 445088.75, "Promedio", 63584.1]
    )
    monkeypatch.setattr(sheets, "_authorized", lambda: fake)

    assert sheets.headers(refresh=True) == ["Invoice", "Salary", "Total"]
    assert fake.posts == []
