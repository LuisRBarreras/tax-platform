#!/usr/bin/env bash
# Report whether the tools and services are in place.
source "$(dirname "$0")/lib.sh"

printf 'python venv : '; [[ -x backend/.venv/bin/python ]] && backend/.venv/bin/python --version || echo "MISSING (make install)"
printf 'node        : '; node --version 2>/dev/null || echo "MISSING"
printf 'pnpm        : '; pnpm --version 2>/dev/null || echo "not found"
printf 'docker      : '; docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',' || echo "not installed"
printf 'database    : '; mysql_exec -N -e "SELECT CONCAT(COUNT(*), ' invoices') FROM invoices;" || echo "not running (make db-up / make start)"
printf 'API         : '; http_ok "http://$HOST:$API_PORT/api/invoices" && echo "up" || echo "down"
printf 'UI          : '; http_ok "http://$HOST:${WEB_PORT}/" && echo "up" || echo "down"
printf 'template    : '; [[ -f backend/resources/template/invoice.html ]] && echo "present" || echo "missing (make template)"
printf 'env file    : '; [[ -f backend/.env ]] && echo "present" || echo "missing (make env)"
