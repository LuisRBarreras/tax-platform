# ============================================================================
#  Invoice Automation — developer commands
#
#  Heavy lifting lives in scripts/ (start, check, smoke, db); this file is just
#  the entry point. Run `make` to see every command.
# ============================================================================

SHELL := /bin/bash

BACKEND  := backend
FRONTEND := frontend
VENV     := $(BACKEND)/.venv
PY       := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
SCRIPTS  := scripts

HOST            ?= 127.0.0.1
API_PORT        ?= 3000
WEB_PORT        ?= 5173
WEB_DOCKER_PORT ?= 8080

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
.PHONY: help install env template start stop check dev api web build \
        test test-api test-web smoke sheet invoices db db-peek migrate \
        db-up docker-up docker-down docker-logs docker-reset clean clean-all

# ---------------------------------------------------------------- lifecycle --
help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "; print ""; print "  Invoice Automation"; print ""} \
	  /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "  UI: http://$(HOST):$(WEB_DOCKER_PORT)   API: http://$(HOST):$(API_PORT)"
	@echo ""

start: ## Start everything in Docker and wait until it answers
	@$(SCRIPTS)/start.sh

stop: ## Stop the stack (keeps the data volumes)
	@docker compose down
	@echo "Stack stopped (data kept in the volumes)."

check: ## Check tools, services and files
	@$(SCRIPTS)/check.sh

install: $(VENV)/.installed ## Install backend and frontend dependencies
	cd $(FRONTEND) && $(PNPM_CMD) install

$(VENV)/.installed: $(BACKEND)/requirements.txt
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r $(BACKEND)/requirements.txt
	@touch $@

env: ## Create backend/.env from the sample when missing
	@[ -f $(BACKEND)/.env ] || cp $(BACKEND)/.env-sample $(BACKEND)/.env
	@echo "backend/.env: $$([ -f $(BACKEND)/.env ] && echo present || echo missing)"

template: ## Create the invoice template from the sample when missing
	@[ -f $(BACKEND)/resources/template/invoice.html ] \
	  || cp $(BACKEND)/resources/template/invoice.sample.html $(BACKEND)/resources/template/invoice.html
	@echo "template: $$([ -f $(BACKEND)/resources/template/invoice.html ] && echo present || echo missing)"

# ---------------------------------------------------------------- local dev --
dev: ## Start API and UI together (Ctrl+C stops both)
	@trap 'kill 0' EXIT INT TERM; \
	  ( cd $(BACKEND) && exec $(CURDIR)/$(PY) -m uvicorn app.main:app --host $(HOST) --port $(API_PORT) ) & \
	  ( cd $(FRONTEND) && exec $(NODE) ./node_modules/vite/bin/vite.js --host $(HOST) --port $(WEB_PORT) ) & \
	  wait

api: ## Start the API (uvicorn)
	cd $(BACKEND) && exec $(CURDIR)/$(PY) -m uvicorn app.main:app --host $(HOST) --port $(API_PORT)

web: ## Start the UI (Vite)
	cd $(FRONTEND) && exec $(NODE) ./node_modules/vite/bin/vite.js --host $(HOST) --port $(WEB_PORT)

build: ## Typecheck + production build of the frontend
	cd $(FRONTEND) && $(PNPM_CMD) run build

# -------------------------------------------------------------------- tests --
test: test-api test-web ## Run both test suites (99 tests)

test-api: ## Backend tests (pytest, needs MySQL)
	@$(PY) -c "import pytest" 2>/dev/null || $(PIP) install --quiet -r $(BACKEND)/requirements-dev.txt
	cd $(BACKEND) && $(CURDIR)/$(PY) -m pytest

test-web: ## Frontend tests (vitest)
	cd $(FRONTEND) && $(PNPM_CMD) run test

smoke: ## Create an invoice and check the main endpoints
	@$(SCRIPTS)/smoke.sh

sheet: ## Check the Google Sheets sync (credentials, tab, columns)
	@$(SCRIPTS)/sheet.sh

# ------------------------------------------------------------------ database --
db: ## Invoice count
	@$(SCRIPTS)/db.sh count

db-peek: ## Table structure + latest invoices
	@$(SCRIPTS)/db.sh peek

invoices: ## Latest 20 invoices
	@$(SCRIPTS)/db.sh list

migrate: ## Import invoices from the old SQLite file into MySQL
	cd $(BACKEND) && $(CURDIR)/$(PY) scripts/migrate_sqlite_to_mysql.py

db-up: ## Start the standalone MySQL container (dev without Docker for the app)
	@$(SCRIPTS)/db-up.sh

# -------------------------------------------------------------------- docker --
docker-up: ## Build and start the stack
	docker compose up -d --build

docker-down: ## Stop the stack
	docker compose down

docker-logs: ## Follow the stack logs
	docker compose logs -f --tail=100

docker-reset: ## Stop the stack and delete the data volumes (destructive)
	docker compose down -v

# --------------------------------------------------------------------- clean --
clean: ## Remove caches and build artifacts
	rm -rf $(BACKEND)/__pycache__ $(BACKEND)/app/__pycache__ $(BACKEND)/scripts/__pycache__ \
	       $(BACKEND)/tests/__pycache__ $(BACKEND)/.pytest_cache .pytest_cache \
	       $(FRONTEND)/dist $(FRONTEND)/node_modules/.vite
	@echo "Caches cleared (database, PDFs and proofs are NOT touched)."

clean-all: clean ## Also remove the venv and node_modules
	rm -rf $(VENV) $(FRONTEND)/node_modules
	@echo "Environment removed. Recreate it with 'make install'."
