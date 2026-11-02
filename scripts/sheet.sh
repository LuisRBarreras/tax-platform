#!/usr/bin/env bash
# Check the Google Sheets wiring (credentials, tab access, column mapping).
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

if docker ps --format '{{.Names}}' | grep -qx "tax-platform-api"; then
  docker exec tax-platform-api python scripts/sheet_check.py
else
  [ -x "$ROOT/backend/.venv/bin/python" ] || die "no venv: run 'make install' first"
  "$ROOT/backend/.venv/bin/python" "$ROOT/backend/scripts/sheet_check.py"
fi
