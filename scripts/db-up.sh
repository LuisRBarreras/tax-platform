#!/usr/bin/env bash
# Start the standalone MySQL container used when the app runs outside Docker.
source "$(dirname "$0")/lib.sh"

if docker start tax-platform-mysql >/dev/null 2>&1; then
  ok "started existing tax-platform-mysql"
else
  docker run -d --name tax-platform-mysql -p "127.0.0.1:3306:3306" \
    -e MYSQL_ROOT_PASSWORD=devroot \
    -e MYSQL_DATABASE=tax_platform \
    -e MYSQL_USER=tax \
    -e MYSQL_PASSWORD=taxpass \
    -v tax_platform_mysql:/var/lib/mysql mysql:8.4 >/dev/null
  ok "created tax-platform-mysql"
fi

wait_for "MySQL" "http://127.0.0.1:3306" 1 1 >/dev/null 2>&1 || true
log "MySQL on 127.0.0.1:3306 (database tax_platform, user tax)"
