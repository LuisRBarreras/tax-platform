#!/usr/bin/env bash
# Start the whole stack and wait until it answers.
source "$(dirname "$0")/lib.sh"

ensure_env
ensure_template

log "building and starting containers..."
docker compose up -d --build

wait_for "the API" "http://$HOST:$API_PORT/api/invoices" 90 2 \
  || die "the API did not answer - check 'make docker-logs'"
wait_for "the UI" "http://$HOST:$WEB_PORT/" 30 2 \
  || die "the UI did not answer - check 'make docker-logs'"

echo
ok "ready to use"
log ""
log "  UI    -> http://$HOST:$WEB_PORT"
log "  API   -> http://$HOST:$API_PORT"
log "  docs  -> http://$HOST:$API_PORT/docs"
log ""

command -v open >/dev/null 2>&1 && open "http://$HOST:$WEB_PORT" || true
