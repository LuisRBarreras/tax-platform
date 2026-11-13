#!/usr/bin/env bash
# Empty the invoices table and the generated files. Destructive: takes a dump
# first and asks for confirmation unless it is called with -y.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ASSUME_YES=0
[ "${1:-}" = "-y" ] && ASSUME_YES=1

count=$(mysql_exec -N -B -e "SELECT COUNT(*) FROM invoices;" 2>/dev/null) || count="?"
api_up=0
docker ps --format '{{.Names}}' | grep -qx "tax-platform-api" && api_up=1
files=$([ "$api_up" = 1 ] && docker exec tax-platform-api sh -c \
  'find /app/.tmp/invoices /app/.tmp/proofs /app/.tmp/outbox -type f 2>/dev/null | wc -l' 2>/dev/null || echo "?")

log "invoices : $count"
log "archivos : $files (PDFs, comprobantes y .eml)"

if [ "$ASSUME_YES" -ne 1 ]; then
  printf 'Se borra todo y no hay vuelta atrás. Escribe "si" para continuar: '
  read -r answer
  [ "$answer" = "si" ] || die "cancelado"
fi

# 1. Dump first: one file, cheap insurance.
if [ "$count" != "0" ] && [ "$count" != "?" ]; then
  mkdir -p "$ROOT/backend/data/backups"
  dump="$ROOT/backend/data/backups/invoices-$(date +%Y%m%d-%H%M%S).sql"
  docker exec tax-platform-db mysqldump "-u$MYSQL_USER" "-p$MYSQL_PASSWORD" "$MYSQL_DATABASE" invoices \
    > "$dump" 2>/dev/null && ok "respaldo: ${dump#$ROOT/}"
fi

# 2. Rows.
mysql_exec -e "DELETE FROM invoices;" || die "no se pudo vaciar la tabla"

# 3. Generated files (a fresh database must not point at orphans).
if [ "$api_up" = 1 ]; then
  docker exec tax-platform-api sh -c \
    'rm -rf /app/.tmp/invoices/* /app/.tmp/proofs/* /app/.tmp/outbox/*' 2>/dev/null || true
else
  warn "el API no está corriendo: los archivos de .tmp se quedaron"
fi

left=$(mysql_exec -N -B -e "SELECT COUNT(*) FROM invoices;" 2>/dev/null)
ok "base vacía ($left filas)"
