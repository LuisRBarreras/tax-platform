"""Append one row to the invoice tracker spreadsheet after an email is sent.

The row is built from the tab's own header row, so the column order and the
extra columns of the spreadsheet are respected without hardcoding them: only
the headers we recognise get a value, anything else stays empty.

Only `google-auth` and `requests` are used (both already pinned), so no extra
client library is added to the image.

A failure here is never fatal: by the time we append, the email is already out,
so `record_send` reports the problem instead of raising.
"""
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from . import config
from . import emailer

API = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Value used when the tab has no header row yet: same columns as the email.
DEFAULT_COLUMNS = ["period", "deposit", "salary", "rate", "pesos"]

# Header aliases, already normalised (lowercase, no accents, single spaces).
ALIASES: Dict[str, tuple] = {
    "period": ("fecha trabajo", "fecha de trabajo", "periodo", "work period", "work date"),
    "deposit": ("fecha deposito", "fecha de deposito", "deposit date", "fecha pago"),
    "salary": ("salary", "salario", "sueldo"),
    "rate": ("tipo de cambio", "tipo cambio", "exchange rate", "t c", "tc"),
    "pesos": ("pesos", "mxn", "pesos mexicanos"),
    "invoice": ("invoice", "invoice no", "invoice number", "no invoice", "factura", "no factura"),
    "client": ("client", "cliente"),
    "sent": (
        "factura enviada",
        "enviado",
        "enviada",
        "sent",
        "fecha envio",
        "sent at",
        "sent date",
    ),
}


class SheetError(RuntimeError):
    """Problem talking to the spreadsheet, already phrased for the user."""


_session = None
_headers: Optional[List[str]] = None


# --------------------------------------------------------------- helpers --
def _normalize(text: Any) -> str:
    """'Fecha  Depósito' -> 'fecha deposito'."""
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(plain.lower().replace("#", " ").replace(":", " ").split())


def _match(header: str) -> Optional[str]:
    """Map a spreadsheet header to one of our known fields."""
    label = _normalize(header)
    for key, aliases in ALIASES.items():
        if label in aliases:
            return key
    return None


def credentials_path() -> Path:
    """Absolute path of the service account file (relative to backend/)."""
    raw = config.GOOGLE_APPLICATION_CREDENTIALS.strip()
    if not raw:
        raise SheetError(
            "Falta GOOGLE_APPLICATION_CREDENTIALS en backend/.env "
            "(ruta al archivo de la cuenta de servicio)."
        )
    path = Path(raw)
    return path if path.is_absolute() else Path(config.BACKEND_DIR) / path


def spreadsheet_id() -> str:
    book = config.GOOGLE_SPREADSHEET_ID.strip()
    if not book:
        raise SheetError("Falta GOOGLE_SPREADSHEET_ID en backend/.env.")
    return book


def tabs() -> Dict[int, str]:
    """{gid: title} of every tab in the spreadsheet."""
    session = _authorized()
    response = session.get(
        f"{API}/{spreadsheet_id()}",
        params={"fields": "sheets.properties(sheetId,title)"},
        timeout=15,
    )
    if response.status_code != 200:
        raise SheetError(_explain(response))
    return {
        int(sheet["properties"]["sheetId"]): sheet["properties"]["title"]
        for sheet in response.json().get("sheets", [])
    }


def tab_name() -> str:
    """Title of the target tab.

    When a gid is configured it wins over the name, and the two must agree: the
    gid is what the spreadsheet URL points at, so a mismatch means the name and
    the link speak about different tabs. Failing loudly here is deliberate —
    writing to the wrong tab is worse than not writing at all.
    """
    name = config.GOOGLE_SHEETS_TAB.strip()
    gid = config.GOOGLE_SHEETS_GID.strip()

    if not gid:
        if not name:
            raise SheetError(
                "Falta GOOGLE_SHEETS_TAB en backend/.env: el tab que recibe las "
                "filas no está configurado y no hay default."
            )
        return name

    try:
        known = tabs()
    except SheetError:
        if not name:
            raise
        return name  # no metadata: trust the configured name

    if int(gid) not in known:
        raise SheetError(f"El gid {gid} no existe en la hoja.")
    title = known[int(gid)]
    if name and name != title:
        raise SheetError(
            f"GOOGLE_SHEETS_TAB dice '{name}' pero el gid {gid} es el tab "
            f"'{title}'. Ajusta uno de los dos en backend/.env; no escribo "
            "hasta saber cuál es el correcto."
        )
    return title


def sheet_url(book: str = "") -> str:
    """Deep link to the document, on the configured tab when its gid is known."""
    url = f"https://docs.google.com/spreadsheets/d/{book or config.GOOGLE_SPREADSHEET_ID}/edit"
    gid = config.GOOGLE_SHEETS_GID.strip()
    return f"{url}#gid={gid}" if gid else url


def _authorized():
    """Authorised session, created once and reused."""
    global _session
    if _session is not None:
        return _session

    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    path = credentials_path()
    if not path.exists():
        raise SheetError(f"No se encontró la credencial de servicio: {path}")
    try:
        credentials = service_account.Credentials.from_service_account_file(
            str(path), scopes=SCOPES
        )
    except Exception as exc:
        raise SheetError(f"Credenciales de Google inválidas ({path}): {exc}")
    _session = AuthorizedSession(credentials)
    return _session


def _explain(response) -> str:
    """Turn a Sheets API error into something actionable."""
    try:
        error = response.json().get("error", {})
        message = error.get("message", "")
        reasons = {
            detail.get("reason")
            for detail in error.get("details", [])
            if isinstance(detail, dict)
        }
    except Exception:
        return f"Google Sheets respondió {response.status_code}"

    if "SERVICE_DISABLED" in reasons:
        return (
            "La API de Google Sheets está deshabilitada en el proyecto. "
            "Actívala en la consola de Google Cloud y vuelve a intentar."
        )
    if response.status_code == 403:
        return (
            "La cuenta de servicio no tiene permiso sobre la hoja. "
            "Compártela como Editor con la cuenta de servicio."
        )
    if response.status_code == 404:
        # Not tab_name(): it talks to the API and _explain must not recurse.
        target = config.GOOGLE_SHEETS_TAB or f"gid {config.GOOGLE_SHEETS_GID}"
        return f"No se encontró la hoja o el tab '{target}'."
    return f"Google Sheets respondió {response.status_code}: {message}"


def _values(range_a1: str) -> List[List[Any]]:
    session = _authorized()
    response = session.get(
        f"{API}/{spreadsheet_id()}/values/{quote(range_a1, safe='')}",
        params={"majorDimension": "ROWS", "valueRenderOption": "UNFORMATTED_VALUE"},
        timeout=15,
    )
    if response.status_code != 200:
        raise SheetError(_explain(response))
    return response.json().get("values", [])


# ------------------------------------------------------------------ data --
def headers(refresh: bool = False) -> List[str]:
    """Header row of the configured tab (cached for the process).

    The tab has a totals block to the right of the table (SUM/Promedio in row 1);
    those cells are numbers, so the header row stops at the first non-text cell
    instead of pretending the totals are columns.
    """
    global _headers
    if _headers is not None and not refresh:
        return _headers

    rows = _values(f"'{tab_name()}'!A1:1")
    row = rows[0] if rows else []
    labels: List[str] = []
    for cell in row:
        if not isinstance(cell, str):
            break
        labels.append(cell.strip())
    _headers = labels
    return _headers


def row_values(invoice: Dict[str, Any], sent_at: str = "") -> Dict[str, Any]:
    """The values we know how to fill, keyed by our field names."""
    return {
        "period": emailer.work_period(invoice.get("work-from", ""), invoice.get("work-to", "")),
        "deposit": emailer.short_date(invoice.get("deposit-date", "")),
        "salary": round(float(invoice.get("total") or 0), 2),
        "rate": float(invoice.get("exchange-rate") or 0),
        "pesos": round(emailer.pesos(invoice), 2),
        "invoice": invoice.get("invoice-number") or invoice.get("invoice-id", ""),
        "client": invoice.get("client-name", ""),
        # The "Factura enviada" column of the tracker is a Si/No flag.
        "sent": "Si" if sent_at else "",
    }


def build_row(
    invoice: Dict[str, Any], sent_at: str = "", header_row: Optional[List[str]] = None
) -> List[Any]:
    """One row aligned with the tab's header row."""
    known = row_values(invoice, sent_at)
    header_row = headers() if header_row is None else header_row
    if not header_row:
        return [known[key] for key in DEFAULT_COLUMNS]
    return [known.get(_match(header), "") for header in header_row]


def _trim(values: List[Any]) -> List[Any]:
    """Drop trailing blanks so we never write into the summary columns."""
    last = len(values)
    while last and values[last - 1] == "":
        last -= 1
    return values[:last]


def append_row(
    invoice: Dict[str, Any], sent_at: str = ""
) -> Dict[str, Any]:
    """Append the invoice row to the first empty row of the tab."""
    book = spreadsheet_id()
    if _headers is None:
        headers()  # raises SheetError when the sheet cannot be read
    row = _trim(build_row(invoice, sent_at))
    range_a1 = f"'{tab_name()}'!A1"

    session = _authorized()
    response = session.post(
        f"{API}/{book}/values/{quote(range_a1, safe='')}:append",
        params={
            "valueInputOption": "USER_ENTERED",
            "insertDataOption": "INSERT_ROWS",
        },
        json={"values": [row]},
        timeout=20,
    )
    if response.status_code not in (200, 201):
        raise SheetError(_explain(response))

    updates = response.json().get("updates", {})
    return {
        "status": "appended",
        "tab": tab_name(),
        "range": updates.get("updatedRange", ""),
        "url": sheet_url(book),
    }


def record_send(
    invoice: Dict[str, Any], sent_at: str = "", recipient: str = ""
) -> Dict[str, Any]:
    """Append the row and report what happened. Never raises."""
    if not config.GOOGLE_SHEETS_ENABLED:
        return {"status": "disabled", "message": "GOOGLE_SHEETS_ENABLED=0"}
    if emailer.is_dry_run():
        return {"status": "skipped", "message": "Modo prueba (SMTP_DRY_RUN=1)"}

    try:
        result = append_row(invoice, sent_at)
    except SheetError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:  # network, JSON, credentials...
        return {"status": "error", "message": f"{type(exc).__name__}: {exc}"}

    result["to"] = recipient
    return result


def status() -> Dict[str, Any]:
    """Diagnostics for `make sheet`: can we read the tab, and what is in it?"""
    info: Dict[str, Any] = {
        "credentials": str(credentials_path()),
        "spreadsheet": config.GOOGLE_SPREADSHEET_ID,
        "tab": config.GOOGLE_SHEETS_TAB,
        "gid": config.GOOGLE_SHEETS_GID,
        "enabled": config.GOOGLE_SHEETS_ENABLED,
        "url": sheet_url(),
    }
    try:
        tab = tab_name()
        header_row = headers(refresh=True)
        rows = _values(f"'{tab}'!A:A")
        info["tab"] = tab
        info["headers"] = header_row
        info["mapping"] = {header: _match(header) for header in header_row}
        info["rows"] = max(len(rows) - 1, 0) if rows else 0
        info["ok"] = True
    except SheetError as exc:
        info["ok"] = False
        info["error"] = str(exc)
    return info
