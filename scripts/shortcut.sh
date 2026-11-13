#!/usr/bin/env bash
# Put a double-clickable launcher on the Desktop.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TARGET="$HOME/Desktop/Invoice.command"

[ -d "$HOME/Desktop" ] || die "no hay ~/Desktop en este sistema"
[ -f "$ROOT/scripts/launch.command" ] || die "falta scripts/launch.command"

cp "$ROOT/scripts/launch.command" "$TARGET"
chmod +x "$TARGET"
ok "shortcut: $TARGET"
log "  doble clic para levantar la app (o arrástralo al Dock)"
