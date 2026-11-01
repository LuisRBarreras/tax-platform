# ============================================================================
#  Invoice Automation — development commands
#
#  make            -> this help
#  make install    -> dependencies (Python venv + node_modules)
#  make dev        -> API (:3000) and UI (:5173) together
#  make smoke      -> creates an invoice and checks listing / PDF / HTML
# ============================================================================

SHELL := /bin/bash

BACKEND  := backend
FRONTEND := frontend
VENV     := $(BACKEND)/.venv
PY       := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
DB       := $(BACKEND)/data/invoices.db

TEMPLATE        := $(BACKEND)/resources/template/invoice.html
TEMPLATE_SAMPLE := $(BACKEND)/resources/template/invoice.sample.html

API_PORT ?= 3000
WEB_PORT ?= 5173
HOST     ?= 127.0.0.1

# Node: the system one is v16 and Vite 7 needs 20+. Prefer .tooling/node,
# re-signed ad-hoc so macOS allows loading native addons.
NODE ?= $(or $(wildcard $(CURDIR)/.tooling/node),$(shell command -v node))

# pnpm: the one in PATH, or the DSH runtime copy if there is none.
PNPM ?= $(shell command -v pnpm 2>/dev/null || echo /Users/luisbarreras/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/pnpm/bin/pnpm.mjs)
ifeq ($(suffix $(PNPM)),.mjs)
  PNPM_CMD := $(NODE) $(PNPM)
else
  PNPM_CMD := $(PNPM)
endif

# Make pnpm and vite resolve `node` to the local one, not the system v16.
export PATH := $(CURDIR)/.tooling:$(PATH)

.DEFAULT_GOAL := help
.PHONY: help install env template check api api-reload web dev build test smoke test-invoice \
        db db-peek invoices migrate clean clean-all

# ---------------------------------------------------------------- help ------
help: ## Show this help
	@echo ""
	@echo "  Invoice Automation"
	@echo ""
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  API: http://$(HOST):$(API_PORT)   UI: http://$(HOST):$(WEB_PORT)"
	@echo ""

# --------------------------------------------------------------- install ----
install: $(VENV)/.installed ## Install backend and frontend dependencies
	cd $(FRONTEND) && $(PNPM_CMD) install

$(VENV)/.installed: $(BACKEND)/requirements.txt
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r $(BACKEND)/requirements.txt
	@touch $@

env: ## Create backend/.env from .env-sample when missing
	@if [ -f $(BACKEND)/.env ]; then \
	  echo "backend/.env already exists - leaving it alone."; \
	else \
	  cp $(BACKEND)/.env-sample $(BACKEND)/.env; \
	  echo "Created backend/.env from .env-sample (SMTP_DRY_RUN=1: no emails sent)."; \
	  echo "Fill in SMTP_USER / SMTP_PASSWORD / MAIL_FROM for real sending."; \
	fi

template: ## Create the invoice template from the sample when missing
	@if [ -f $(TEMPLATE) ]; then \
	  echo "$(TEMPLATE) already exists - leaving it alone."; \
	else \
	  cp $(TEMPLATE_SAMPLE) $(TEMPLATE); \
	  echo "Created $(TEMPLATE) from the sample."; \
	fi

check: ## Check the environment (python, node, pnpm, sqlite, servers)
	@printf "python venv : "; test -x $(PY) && $(PY) --version || echo "MISSING (make install)"
	@printf "node        : "; $(NODE) --version
	@printf "pnpm        : "; $(PNPM) --version 2>/dev/null || echo "not found"
	@printf "sqlite3     : "; command -v sqlite3 >/dev/null && sqlite3 --version | cut -d' ' -f1 || echo "not installed"
	@printf "database    : "; test -f $(DB) && echo "$(DB) ($$(sqlite3 $(DB) 'SELECT COUNT(*) FROM invoices' 2>/dev/null) invoices)" || echo "created when the API starts"
	@printf "API         : "; curl -sf -m 2 http://$(HOST):$(API_PORT)/api/invoices >/dev/null && echo "up" || echo "down"
	@printf "UI          : "; curl -sf -m 2 http://$(HOST):$(WEB_PORT)/ >/dev/null && echo "up" || echo "down"

# --------------------------------------------------------------- servers ----
api: ## Start the API (uvicorn)
	cd $(BACKEND) && exec $(CURDIR)/$(PY) -m uvicorn app.main:app --host $(HOST) --port $(API_PORT)

api-reload: ## Start the API with autoreload
	cd $(BACKEND) && exec $(CURDIR)/$(PY) -m uvicorn app.main:app --host $(HOST) --port $(API_PORT) --reload

web: ## Start the UI (Vite)
	cd $(FRONTEND) && exec $(NODE) ./node_modules/vite/bin/vite.js --host $(HOST) --port $(WEB_PORT)

dev: ## Start API and UI together (Ctrl+C stops both)
	@echo "API → http://$(HOST):$(API_PORT)"
	@echo "UI  → http://$(HOST):$(WEB_PORT)"
	@trap 'kill 0' EXIT INT TERM; \
	  ( cd $(BACKEND) && exec $(CURDIR)/$(PY) -m uvicorn app.main:app --host $(HOST) --port $(API_PORT) ) & \
	  ( cd $(FRONTEND) && exec $(NODE) ./node_modules/vite/bin/vite.js --host $(HOST) --port $(WEB_PORT) ) & \
	  wait

test: ## Run the backend test suite (pytest)
	@$(PY) -c "import pytest" 2>/dev/null || $(PIP) install --quiet -r $(BACKEND)/requirements-dev.txt
	cd $(BACKEND) && exec $(CURDIR)/$(PY) -m pytest

build: ## Typecheck + production build of the frontend (dist/)
	cd $(FRONTEND) && $(PNPM_CMD) run build

# ----------------------------------------------------------------- tests ----
smoke: ## Create an invoice and verify listing, PDF and HTML against the API
	@curl -sf -m 3 http://$(HOST):$(API_PORT)/api/invoices >/dev/null \
	  || { echo "The API is not responding on :$(API_PORT). Start it with 'make api'."; exit 1; }
	@echo "== POST /api/invoices =="
	@ID=$$(curl -s -X POST http://$(HOST):$(API_PORT)/api/invoices \
	    -H "Content-Type: application/json" \
	    -d '{"date":"'$$(date +%Y-%m-%d)'","items":[{"description":"Software Service","quantity":1,"unit-price":3600}]}' \
	  | tee /tmp/invoice_smoke.json | $(PY) -c "import sys,json; print(json.load(sys.stdin)['invoice-id'])"); \
	  echo "   id: $$ID"; \
	  echo "== GET endpoints =="; \
	  printf "   listing : %s\n" "$$(curl -s -o /dev/null -w '%{http_code}' http://$(HOST):$(API_PORT)/api/invoices)"; \
	  printf "   detail  : %s\n" "$$(curl -s -o /dev/null -w '%{http_code}' http://$(HOST):$(API_PORT)/api/invoices/$$ID)"; \
	  printf "   PDF     : %s\n" "$$(curl -s -o /tmp/invoice_smoke.pdf -w '%{http_code} %{content_type}' http://$(HOST):$(API_PORT)/api/invoices/$$ID/pdf) ($$(wc -c < /tmp/invoice_smoke.pdf | tr -d ' ') bytes)"; \
	  printf "   HTML    : %s\n" "$$(curl -s -o /dev/null -w '%{http_code} %{content_type}' http://$(HOST):$(API_PORT)/api/invoices/$$ID/html)"; \
	  printf "   bad id  : %s (expected 404)\n" "$$(curl -s -o /dev/null -w '%{http_code}' 'http://$(HOST):$(API_PORT)/api/invoices/..%%2F..%%2Fetc/html')"

test-invoice: smoke ## Alias of smoke

# --------------------------------------------------------------- database ---
db: ## SQLite path and size
	@test -f $(DB) \
	  && echo "$(DB) - $$(sqlite3 $(DB) 'SELECT COUNT(*) FROM invoices') invoices, $$(du -h $(DB) | cut -f1)" \
	  || echo "$(DB) does not exist yet (created when the API starts)"

db-peek: ## Schema + latest invoices via sqlite3
	@test -f $(DB) || { echo "$(DB) does not exist"; exit 1; }
	@sqlite3 -header -column $(DB) "PRAGMA table_info(invoices);"
	@echo "---"
	@sqlite3 -header -column $(DB) "SELECT substr(id,1,18) AS id, date, printf('%.2f', total) AS total, status FROM invoices ORDER BY date DESC, created_at DESC LIMIT 10;"

invoices: ## List the latest 20 invoices
	@test -f $(DB) || { echo "$(DB) does not exist"; exit 1; }
	@sqlite3 -header -column $(DB) "SELECT substr(id,1,18) AS id, date, printf('%.2f', total) AS total, status, pdf_path IS NOT NULL AS pdf FROM invoices ORDER BY date DESC, created_at DESC LIMIT 20;"

migrate: ## Import old invoices (Mongo/JSON) into SQLite
	cd $(BACKEND) && $(CURDIR)/$(PY) scripts/migrate_to_sqlite.py

# ----------------------------------------------------------------- clean ----
clean: ## Remove caches and build artifacts
	rm -rf $(BACKEND)/__pycache__ $(BACKEND)/app/__pycache__ \
	       $(BACKEND)/scripts/__pycache__ $(BACKEND)/.pytest_cache .pytest_cache \
	       $(FRONTEND)/dist $(FRONTEND)/node_modules/.vite
	@echo "Caches cleared (database and PDFs are NOT touched)."

clean-all: clean ## Also remove venv and node_modules
	rm -rf $(VENV) $(FRONTEND)/node_modules
	@echo "Environment removed. Recreate it with 'make install'."
