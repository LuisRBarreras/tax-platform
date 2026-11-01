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
| Data | SQLite (stdlib `sqlite3`, no ORM) |
| PDF | Jinja2 + WeasyPrint, HTML template + embedded Noto Sans fonts |
| Email | `smtplib` + `email` (MIME multipart, attachments) |
| Frontend | React 19 + Vite 7 + TypeScript |

## Getting started

```bash
make install     # Python venv + node_modules
make env         # create backend/.env from .env-sample when missing
make template    # create the PDF template from invoice.sample.html
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
│   ├── db.py             SQLite schema and migrations
│   ├── invoice_store.py  queries + pagination
│   ├── invoice.py        business rules
│   ├── pdf.py            template rendering + WeasyPrint
│   └── emailer.py        MIME, attachments, SMTP and preview
├── resources/
│   ├── template/
│   │   ├── invoice.sample.html generic template (versioned)
│   │   └── invoice.html        real template (gitignored, `make template`)
│   └── fonts/                  Noto Sans (extracted from the original invoice)
├── scripts/migrate_to_sqlite.py
├── data/invoices.db      database (gitignored)
└── .tmp/                 PDFs, proofs and test emails (gitignored)
frontend/
└── src/                  wizard, paginated list and modals
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
| `POST` | `/api/invoices/{id}/send` | Sends the email (`{to, subject}`) |
| `GET` | `/api/mail/recipients` | Allowed recipients and dry-run status |

Interactive docs: **http://127.0.0.1:3000/docs**

## Data

One row per invoice in `backend/data/invoices.db`:

- `id` (`INV-<uuid>`, internal key), `number` (the number you type and the PDF shows)
- dates: `date`, `work_from`, `work_to`, `deposit_date`
- amounts: `total` (USD), `exchange_rate`, `pesos` (`NULL` = compute `total × rate`)
- status: `status` (`created` / `sent`), `sent_at`, `sent_to`
- `items_json`, `pdf_path`, `proof_path`, `created_at`

Files live outside the database, under `backend/.tmp/`: the database only stores their
paths. That keeps the door open for moving PDFs to S3 by changing `pdf_path`, with no
schema change.

## Commands

```
make              list every command
make dev          API + UI
make smoke        creates an invoice and checks listing, detail, PDF, HTML and 404
make invoices     latest 20 invoices as a table
make db           database path and size
make db-peek      schema + latest 10 invoices
make migrate      import old invoices (Mongo/JSON) into SQLite
make build        typecheck + frontend build
make clean        caches (never touches the database or the PDFs)
```

## Conventions

- **Code, comments and documentation in English.**
- **User-facing text in Spanish**: UI labels, API messages and the email body, because
  the person using it and the client receiving it are Spanish speakers.
- The invoice template itself is in English (`INVOICE`, `DESCRIPTION / MEMO`, `AMOUNT`)
  because it mirrors the client's original document.

## Known limitations

- **No authentication.** The API listens on `127.0.0.1`; meant for local use.
- **Single client.** Client data comes from `.env`, not from the database.
- **No backup.** `.tmp/` and `data/` are gitignored and there is no scheduled backup.
- **Old PDFs are not regenerated** when the template changes: the preview always uses the
  current template, but a stored PDF is the one generated at the time.
- **Subset fonts.** Noto Sans was extracted from the original PDF; it covers the alphabet
  in use, not every glyph.
- **The real template is not versioned.** `invoice.html` is tailored to one client;
  `invoice.sample.html` is a generic layout with the same variables.
