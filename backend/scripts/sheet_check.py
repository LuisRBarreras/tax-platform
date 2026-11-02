#!/usr/bin/env python
"""Check the Google Sheets wiring: credentials, tab access and column mapping.

Run it with `make sheet` (Docker or local venv, whichever is up). It reads the
header row of the configured tab and prints how each column is filled, so a
missing share or a disabled API is obvious instead of showing up as a silent
error while sending an invoice.
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app import sheets  # noqa: E402


def main() -> int:
    info = sheets.status()

    print(f"credentials  : {info['credentials']}")
    print(f"spreadsheet  : {info['spreadsheet'] or '(vacío)'}")
    gid = f" (gid {info['gid']})" if info["gid"] else ""
    print(f"tab          : {info['tab']}{gid}")
    print(f"enabled      : {'yes' if info['enabled'] else 'no (GOOGLE_SHEETS_ENABLED=0)'}")

    if not info["ok"]:
        print(f"error        : {info['error']}")
        print(f"link         : {info['url']}")
        return 1

    print(f"rows         : {info['rows']}")
    print("")
    print("header -> column we fill")

    mapped = 0
    for header, column in info["mapping"].items():
        label = column or "(se deja vacía)"
        if column:
            mapped += 1
        print(f"  {header:<20} -> {label}")

    missing = [name for name in sheets.ALIASES if name not in info["mapping"].values()]
    if missing:
        print("")
        print(f"without a column in the tab: {', '.join(sorted(missing))}")

    print("")
    print(f"{mapped} columns will be filled. link: {info['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
