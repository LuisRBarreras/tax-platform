# Frontend — Invoice Automation

React 19 + Vite 7 + TypeScript. Three-step wizard connected to the real API: creates the
invoice, uploads the payment proof and sends the email.

## Requirements

This Mac has no usable modern Node: the system `node` is v16 and the DeepSeek Harness
runtime has a hardened signature, so both fail to load Rollup's native addons
(`ERR_DLOPEN_FAILED`). The project therefore uses a locally re-signed Node:

```bash
# once, from the repository root
mkdir -p .tooling
cp "$(which node)" .tooling/node      # or any Node 20+/24 you prefer
codesign --force --sign - .tooling/node
```

`.tooling/` is gitignored.

## Commands

```bash
cd frontend
../.tooling/node "$(command -v pnpm)" install   # dependencies
../.tooling/node "$(command -v pnpm)" dev       # http://127.0.0.1:5173
../.tooling/node "$(command -v pnpm)" build     # typecheck + build to dist/
```

On this machine `pnpm` resolves to the binary bundled with DSH:

```bash
PNPM=/Users/luisbarreras/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/pnpm/bin/pnpm.mjs
../.tooling/node "$PNPM" dev
```

Simpler: `make dev` from the repository root starts API and UI together.

## Structure

| File | Role |
|---|---|
| `src/App.tsx` | Loads the paginated list and opens the modals |
| `src/components/Wizard.tsx` | Steps: invoice -> proof -> send |
| `src/components/InvoiceForm.tsx` | Invoice fields (number, dates, amounts) |
| `src/components/InvoiceList.tsx` | Paginated table with created-at timestamps |
| `src/components/ProofUpload.tsx` | Upload button inside the list |
| `src/components/ProofPreview.tsx` | Payment proof modal |
| `src/components/PdfPreview.tsx` | Invoice preview modal (HTML, sandboxed iframe) |
| `src/components/EmailConfirm.tsx` | Email confirmation with attachments |
| `src/components/SendEmailDialog.tsx` | Send flow from a list row |
| `src/invoiceDefaults.ts` | Formatting helpers and today's date |
| `src/api.ts` | HTTP client |
| `src/types.ts` | Mirrors the backend JSON (kebab-case keys) |

## Backend

The UI needs the backend on port 3000 (`vite.config.ts` proxies `/api` there):

```bash
cd ~/code/tax-platform/backend
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 3000
```

Metadata lives in SQLite (`backend/data/invoices.db`), created automatically on startup.
