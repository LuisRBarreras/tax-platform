# AGENTS.md — Working guide for coding agents

## 🎯 General principles

1. **Be pragmatic and methodical.**
   - Prefer simple, direct solutions.
   - Avoid over-engineering.

2. **Split work into small, simple tasks.**
   - One task at a time.
   - Before starting, state what you are going to do and how.

3. **If something is complex, plan first.**
   - Break it into verifiable steps.
   - Verify each step before moving on.
   - Do not assume something worked until you have checked it.

4. **Do not try to do many things in one pass.**
   - Large changes = many small steps.
   - Every change should be reviewable and reversible.

## 📋 Recommended workflow
1. **Understand the context** — read `PLAN.txt` and `SPEC.md` when relevant.
2. **Define the concrete task** — in one or two sentences.
3. **Plan the minimum steps** — a short, verifiable list.
4. **Execute and verify** — implement, test, confirm.
5. **Iterate** — only move to the next task once the previous one is validated.

## 🚫 Clear rules

- **Do not refactor** anything unrelated to the current task.
- **Do not mix** multiple features in one commit.
- **Do not delete** existing functionality without confirming first.
- **Do not modify** a file without reading it first.
- **Verify with tests or curl** every endpoint or relevant change.

## 🔍 Before making changes

- Ask when the scope or direction is unclear.
- Read the target file before editing it.
- Confirm the impact on other modules.

## ✅ Definition of done

- The specific task is implemented.
- Tested and working (manual or automated).
- No unrelated changes.
- The plan (`PLAN.txt`) was updated when applicable.
- It can be explained in a short summary.

---

# Working on tax-platform

## What it is

A local-only tool (no auth, bound to `127.0.0.1`) to issue a monthly invoice to
LoanPro: fill four fields, generate the PDF from an HTML template, attach the
payment proof and email it. Every real send also appends one row to a Google
Sheets tracker.

The UI is a four-step wizard: **Invoice -> Comprobante -> Enviar -> Finalize**.

## Stack

| Layer | What |
|---|---|
| API | Python 3.13, FastAPI, PyMySQL (no ORM), WeasyPrint for the PDF |
| UI | React 19 + Vite + TypeScript, plain CSS in `src/index.css` |
| Data | MySQL 8.4 in Docker; everything runs with `docker compose` (db, api, web) |

## Commands — use these, do not invent equivalents

```
make start      bring the stack up and wait until it answers
make check      tools, services, template and .env present
make test       backend (pytest) + frontend (vitest)
make build      typecheck + production build of the UI
make sheet      Google Sheets wiring: credentials, tab, column mapping
make db         invoice count          make db-peek   latest invoices
make db-wipe    empty the database and .tmp (dumps a backup, asks first)
```

`make test-api` needs MySQL running (`make start` or `make db-up`).

## Conventions

- **Code, comments, commits, docs: English.** User-facing text (UI labels, API
  error messages, email body, wizard steps): **Spanish**. The PDF template: English.
- Logic lives in `app/handlers.py`; `app/routes.py` only maps URLs to handlers.
- No ORM: parameterized SQL in `app/invoice_store.py`, schema in `app/db.py`.
- New setting: `app/config.py` with a safe default **and** a documented entry in
  `backend/.env-sample`. Real values go only in `backend/.env` (gitignored).
- Filters for the PDF (`money`, `usdate`, `invoicedate`) live in `app/pdf.py`.
- Tests never touch SMTP or the real spreadsheet (`SMTP_DRY_RUN=1`,
  `GOOGLE_SHEETS_ENABLED=0` in `tests/conftest.py`).

## Commit style

Imperative, says *what changed* and, in the body, *why*:

```
Let the invoice list delete an invoice
Stop the header row at the totals block
Append each sent invoice to the Google Sheets tracker
```

One feature per commit. Do not mix a fix with a refactor.

## Hard rules (each one comes from a real accident)

- **Never delete rows, files or spreadsheet cells without a backup and an
  explicit confirmation.** `scripts/db-wipe.sh` dumps before deleting; do the same.
- **Google Sheets: send and delete are not symmetric.** Check the target tab by
  **gid and name together** before any write or delete — `tab_name()` refuses to
  work when they disagree, and `deleteDimension` takes a `sheetId`, not a name.
- **No real email, no real sheet write, no destructive command** just to "verify".
  Dry runs, unit tests and `make sheet` cover it; ask first.
- Secrets (`backend/.env`, `backend/resources/service-account-key.json`) are never
  committed, never printed, never copied into the image.

## Definition of done here

- `make test` green and, if the UI changed, `make build`.
- Endpoint or flow touched: exercised with curl or a test, not assumed.
- `PLAN.txt` updated when the change is a decision, not a detail.
- Committed and pushed to `main`.
