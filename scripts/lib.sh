#!/usr/bin/env bash
# Shared helpers for the developer scripts.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HOST="${HOST:-127.0.0.1}"
API_PORT="${API_PORT:-3000}"
WEB_PORT="${WEB_DOCKER_PORT:-8080}"

# Compose database, or the standalone dev container as a fallback.
DB_CONTAINER="${DB_CONTAINER:-tax-platform-db}"
DB_FALLBACK_CONTAINER="${DB_FALLBACK_CONTAINER:-tax-platform-mysql}"
MYSQL_USER="${MYSQL_USER:-tax}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-taxpass}"
MYSQL_DATABASE="${MYSQL_DATABASE:-tax_platform}"

log()  { printf '%s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

http_ok() {
  curl -sf -m 2 "$1" >/dev/null 2>&1
}

wait_for() {
  local label="$1" url="$2" tries="${3:-60}" delay="${4:-2}"
  printf 'waiting for %s' "$label"
  for _ in $(seq 1 "$tries"); do
    if http_ok "$url"; then printf ' ready\n'; return 0; fi
    printf '.'; sleep "$delay"
  done
  printf '\n'; return 1
}

mysql_exec() {
  docker exec -i "$DB_CONTAINER" mysql "-u$MYSQL_USER" "-p$MYSQL_PASSWORD" "$MYSQL_DATABASE" "$@" 2>/dev/null \
    || docker exec -i "$DB_FALLBACK_CONTAINER" mysql "-u$MYSQL_USER" "-p$MYSQL_PASSWORD" "$MYSQL_DATABASE" "$@" 2>/dev/null
}

ensure_env() {
  if [[ ! -f backend/.env ]]; then
    cp backend/.env-sample backend/.env
    ok "created backend/.env from the sample"
  fi
}

ensure_template() {
  if [[ ! -f backend/resources/template/invoice.html ]]; then
    cp backend/resources/template/invoice.sample.html backend/resources/template/invoice.html
    ok "created the invoice template from the sample"
  fi
}
