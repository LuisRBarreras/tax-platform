#!/bin/bash
# Double-click launcher for the invoice app (macOS .command file).
#
# Installed on the Desktop by `make shortcut`; the copy in scripts/ is the
# source of truth. It starts Docker Desktop when it is not running, brings the
# stack up and leaves the browser on the UI. If anything fails the window stays
# open so the message is not lost.
set -uo pipefail

# Works both from scripts/ (the source) and from the Desktop (the copy): use
# the parent folder when it looks like the project, else the default location.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$HERE/../docker-compose.yml" ]; then
  REPO="$(cd "$HERE/.." && pwd)"
else
  REPO="${TAX_PLATFORM_DIR:-$HOME/code/tax-platform}"
fi

pause() {
  printf '\nPulsa Enter para cerrar…'
  read -r _ || true
}

cd "$REPO" 2>/dev/null || {
  echo "✗ No encuentro el proyecto en $REPO"
  pause
  exit 1
}

echo "Invoice App — $REPO"
echo

# 1. Docker has to answer before compose can do anything.
if ! docker info >/dev/null 2>&1; then
  echo "Arrancando Docker Desktop…"
  open -a Docker >/dev/null 2>&1 || true
  printf 'esperando a Docker'
  for _ in $(seq 1 60); do
    if docker info >/dev/null 2>&1; then
      printf ' listo\n'
      break
    fi
    printf '.'
    sleep 2
  done
fi

if ! docker info >/dev/null 2>&1; then
  printf '\n✗ Docker no arrancó. Ábrelo a mano y vuelve a intentar.\n'
  pause
  exit 1
fi

# 2. The stack itself (make start waits for the API and the UI, then opens the browser).
echo
if make start; then
  echo
  echo "✓ Listo. Esta ventana se puede cerrar."
  exit 0
fi

echo
echo "✗ No se pudo levantar. Revisa: make docker-logs"
pause
exit 1
