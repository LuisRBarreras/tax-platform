#!/usr/bin/env bash
# Inspect the invoices table: count | list | peek
source "$(dirname "$0")/lib.sh"

case "${1:-count}" in
  count) mysql_exec -N -e "SELECT CONCAT(COUNT(*), ' invoices') FROM invoices;" || die "MySQL is not running (make db-up / make start)" ;;
  list)  mysql_exec -e "SELECT LEFT(id,18) AS id, number, date, total, status FROM invoices ORDER BY created_at DESC LIMIT 20;" || die "MySQL is not running (make db-up / make start)" ;;
  peek)  mysql_exec -e "DESCRIBE invoices; SELECT LEFT(id,18) AS id, number, date, total, status FROM invoices ORDER BY created_at DESC LIMIT 10;" || die "MySQL is not running (make db-up / make start)" ;;
  *)     die "usage: db.sh [count|list|peek]" ;;
esac
