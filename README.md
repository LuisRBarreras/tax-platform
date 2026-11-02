# Invoice Automation

Local tool to issue the biweekly invoice, attach the payment proof and email it.
It came from a manual routine: build the PDF by hand each period, hunt for the
transfer receipt, and write the email with the period, exchange rate and MXN total.

Today that routine is a three-step wizard plus an API that keeps everything locally.

## The flow

```
1. Invoice      invoice number, date, work period, salary, exchange rate
                -> builds the PDF from the template and stores the invoice
2. Payment      drag the transfer image (or PDF) into the dropzone
3. Send         review the rendered email, pick the recipient, tweak the subject
                and confirm
```

The PDF mirrors the client's original invoice (same fonts, same measurements: see
`backend/resources/template/invoice.html`). The email carries the PDF and the payment
proof as attachments, plus a table with **Work period · Deposit date · Salary ·
Exchange rate · MXN amount**.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13 · FastAPI 0.162 · uvicorn |
| Data | MySQL 8.4 via PyMySQL (no ORM) |
| PDF | Jinja2 + WeasyPrint, HTML template + embedded Noto Sans fonts |
| Email | `smtplib` + `email` (MIME multipart, attachments) |
| Frontend | React 19 + Vite 7 + TypeScript |

## Getting started

### With Docker (everything in containers)

```bash
make start        # env + template, build, start, wait until healthy, open the UI
```

`make start` is idempotent: it creates `backend/.env` and the PDF template if they are
missing, rebuilds only what changed, waits for the API and the UI to answer, then prints
the URLs and opens the browser. `make stop` shuts everything down keeping the volumes.

Open **http://127.0.0.1:8080**. The containers are `tax-platform-db` (MySQL 8.4),
`tax-platform-api` (uvicorn) and `tax-platform-web` (nginx serving the built SPA and
proxying `/api` to the API). Data lives in the `db_data` volume, generated files in
`api_files`.

```bash
make docker-logs     # follow the logs
make docker-down     # stop, keep the database volume
make docker-reset    # stop and delete the volume (destructive)
```

`backend/.env` is mounted read-only into the API container, so secrets never enter the
image; the multi-line address values survive as-is.

### Without Docker (local Python + Node, MySQL in a container)

```bash
make install     # Python venv + node_modules
make env         # create backend/.env from .env-sample when missing
make template    # create the PDF template from invoice.sample.html
make db-up       # MySQL on 127.0.0.1:3306
make dev         # API on :3000 and UI on :5173
```

Open **http://127.0.0.1:5173**.

To send real email, fill these in `backend/.env`:

```bash
SMTP_USER=you@gmail.com
SMTP_PASSWORD=app-password          # 16 characters, not your Google password
MAIL_FROM="Your Name <you@gmail.com>"
SMTP_DRY_RUN=0
```

While `SMTP_DRY_RUN=1` (the default) nothing is sent: the email is written as an
`.eml` file in `backend/.tmp/outbox/` so you can inspect it.

This flag always lives in `backend/.env`, both with and without Docker (the file
is mounted into the container read-only). Docker Compose does not set it, so the
file is the single source of truth. Check the live value with:

```bash
curl -s 127.0.0.1:3000/api/mail/recipients     # {"dry-run":false} means it sends
```

> **macOS note:** the system `node` is v16 and the DeepSeek Harness runtime has a
> hardened signature; neither works for Vite. The project uses `.tooling/node`
> (Node 24 re-signed ad-hoc). Details in `frontend/README.md`.

## Layout

```
backend/
├── app/
│   ├── main.py           creates the app and registers the router
│   ├── routes.py         URLs -> handlers (10 endpoints)
│   ├── handlers.py       logic: invoices, payment proofs and email
│   ├── schemas.py        Pydantic request models
│   ├── config.py         settings from .env
│   ├── db.py             MySQL schema and migrations
│   ├── invoice_store.py  queries + pagination
│   ├── invoice.py        business rules
│   ├── pdf.py            template rendering + WeasyPrint
│   ├── emailer.py        MIME, attachments, SMTP and preview
│   └── sheets.py         appends the sent invoice to the Google Sheet
├── resources/
│   ├── template/
│   │   ├── invoice.sample.html generic template (versioned)
│   │   └── invoice.html        real template (gitignored, `make template`)
│   └── fonts/                  Noto Sans (extracted from the original invoice)
├── scripts/
│   ├── migrate_sqlite_to_mysql.py
│   └── sheet_check.py    `make sheet` diagnostics
├── Dockerfile
└── .tmp/                 PDFs, proofs and test emails (gitignored)
frontend/
├── Dockerfile
├── nginx.conf            serves the SPA and proxies /api
└── src/                  wizard, paginated list and modals
docker-compose.yml        db + api + web
docker/mysql-init.sql     test database and grants
```

## API

| Method | Route | What it does |
|---|---|---|
| `POST` | `/api/invoices` | Creates the invoice and builds the PDF |
| `GET` | `/api/invoices?page=&per_page=` | Paginated list (newest first) |
| `GET` | `/api/invoices/{id}` | Single invoice |
| `GET` | `/api/invoices/{id}/pdf` | Downloads the PDF |
| `GET` | `/api/invoices/{id}/html` | Rendered invoice (preview) |
| `POST` | `/api/invoices/{id}/upload-proof` | Uploads the payment proof (multipart, field `proof`) |
| `GET` | `/api/invoices/{id}/proof` | Returns the payment proof |
| `GET` | `/api/invoices/{id}/email-preview` | Rendered email, nothing is sent |
| `POST` | `/api/invoices/{id}/send` | Sends the email (`{to, subject}`) and appends the sheet row |
| `GET` | `/api/mail/recipients` | Allowed recipients and dry-run status |

Interactive docs: **http://127.0.0.1:3000/docs**

## Data

One row per invoice in the `invoices` table (MySQL):

- `id` (`INV-<uuid>`, internal key), `number` (the number you type and the PDF shows)
- dates: `date`, `work_from`, `work_to`, `deposit_date`
- amounts: `total` (USD), `exchange_rate`, `pesos` (`NULL` = compute `total × rate`)
- status: `status` (`created` / `sent`), `sent_at`, `sent_to`
- `items_json`, `pdf_path`, `proof_path`, `created_at`

Files live outside the database, under `backend/.tmp/` (a volume in Docker): the database
only stores their paths. That keeps the door open for moving PDFs to S3 by changing
`pdf_path`, with no schema change.

## Spreadsheet

Each invoice that is really sent appends **one row** to the tab configured in
`backend/.env` (`GOOGLE_SHEETS_TAB`, required — there is no default in the code).

```bash
make sheet     # does the tab answer? which column gets which value?
```

```
credentials  : /app/resources/service-account-key.json
spreadsheet  : 1i6cydbN9TD5Ebpr4ZLNSpMWC41f5xornMmhLMB3WbUQ
tab          : Copy of 2026
enabled      : yes
rows         : 57

header -> column we fill
  Fecha Trabajo        -> period
  Fecha Depósito       -> deposit
  Salary               -> salary
  Tipo de cambio       -> rate
  Pesos                -> pesos
  Comentarios          -> (se deja vacía)
```

Three things have to be true, and `make sheet` tells you which one is missing:

1. the **Google Sheets API** is enabled in the Cloud project of the service account;
2. the spreadsheet is **shared as Editor** with the service account email
   (it is inside `resources/service-account-key.json`, field `client_email`);
3. the credentials file exists locally and in the container (compose mounts it
   read-only; it is never baked into the image).

The row follows the tab's own header row: the columns are matched by name
(`Fecha Depósito` = `fecha deposito` = `deposit date`), the order does not
matter and any column we do not recognise is left empty. If the tab has no
header yet, the five columns of the email table are used.

The spreadsheet is always secondary: if it fails, the email is still sent and
the UI shows *"El correo salió, pero no se pudo guardar en el spreadsheet"*.
`SMTP_DRY_RUN=1` never appends anything.

## Commands

The Makefile is deliberately thin: anything longer than a couple of lines lives in
`scripts/` (`start.sh`, `check.sh`, `smoke.sh`, `db.sh`, `db-up.sh`, plus `lib.sh` with the
shared helpers).

```
make              list every command
make start        everything in Docker, ready to use
make stop         stop the stack
make dev          API + UI
make smoke        creates an invoice and checks listing, detail, PDF, HTML and 404
make sheet        checks the Google Sheets sync (credentials, tab, columns)
make invoices     latest 20 invoices as a table
make db-up        start the local MySQL container (dev without Docker for the app)
make docker-up    build and start the whole stack
make db           invoices stored in MySQL
make db-peek      table structure + latest 10 invoices
make migrate      import invoices from the old SQLite file into MySQL
make build        typecheck + frontend build
make clean        caches (never touches the database or the PDFs)
```

## Tests

```bash
make test        # backend + frontend (116 tests, ~4 s)
make test-api    # pytest only (83)
make test-web    # vitest only (33)
```

**Backend** runs against a throwaway MySQL database (`tax_platform_test`) and a temporary
working directory, with email in dry-run. The database is dropped and the directory removed
when the session ends, so it never touches the real data or the network. MySQL must be
running (`make db-up` or `make docker-up`).

| File | Covers |
|---|---|
| `tests/test_invoice.py` | totals, ids, date fallback, client defaults, pesos override |
| `tests/test_invoice_store.py` | save/get roundtrip, upsert, ordering, pagination, sent state, delete |
| `tests/test_pdf.py` | money/qty/date filters, invoice number fallback, **HTML escaping** |
| `tests/test_emailer.py` | periods, pesos, subject override, header injection, attachments, dry run |
| `tests/test_api.py` | every endpoint: status codes, pagination, upload limits, allowlist, security headers |

**Frontend** uses Vitest + Testing Library in jsdom:

| File | Covers |
|---|---|
| `src/invoiceDefaults.test.ts` | work-period formatting, short dates, local today |
| `src/api.test.ts` | URL builders |
| `src/components/InvoiceForm.test.tsx` | validation gating, pesos auto-calc and manual override, payload, error state |
| `src/components/InvoiceList.test.tsx` | rows, Spanish status labels, pagination, empty state, proof preview |

Test-only dependencies: `backend/requirements-dev.txt` and the frontend devDependencies
(`vitest`, `jsdom`, `@testing-library/*`).

## Conventions

- **Code, comments and documentation in English.**
- **User-facing text in Spanish**: UI labels, API messages and the email body, because
  the person using it and the client receiving it are Spanish speakers.
- The invoice template itself is in English (`INVOICE`, `DESCRIPTION / MEMO`, `AMOUNT`)
  because it mirrors the client's original document.

## Known limitations

- **No authentication.** The API listens on `127.0.0.1`; meant for local use.
- **Single client.** Client data comes from `.env`, not from the database.
- **No backup.** The MySQL volume and `.tmp/` have no scheduled backup.
- **Old PDFs are not regenerated** when the template changes: the preview always uses the
  current template, but a stored PDF is the one generated at the time.
- **Subset fonts.** Noto Sans was extracted from the original PDF; it covers the alphabet
  in use, not every glyph.
- **The real template is not versioned.** `invoice.html` is tailored to one client;
  `invoice.sample.html` is a generic layout with the same variables.
