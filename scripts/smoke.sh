#!/usr/bin/env bash
# Create one invoice and exercise the main endpoints.
source "$(dirname "$0")/lib.sh"

base="http://$HOST:$API_PORT"
http_ok "$base/api/invoices" || die "the API is not answering on :$API_PORT (make start)"

echo "== POST /api/invoices =="
payload=$(printf '{"date":"%s","work-from":"%s","work-to":"%s","deposit-date":"%s","exchange-rate":18.5,"items":[{"description":"Software Service","quantity":1,"unit-price":3600}]}' \
  "$(date +%Y-%m-%d)" "$(date +%Y-%m-01)" "$(date +%Y-%m-%d)" "$(date +%Y-%m-%d)")

response=$(curl -s -X POST "$base/api/invoices" -H 'Content-Type: application/json' -d "$payload")
invoice_id=$(printf '%s' "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['invoice-id'])")
echo "   id: $invoice_id"

echo "== GET endpoints =="
printf "   listing : %s\n" "$(curl -s -o /dev/null -w '%{http_code}' "$base/api/invoices")"
printf "   detail  : %s\n" "$(curl -s -o /dev/null -w '%{http_code}' "$base/api/invoices/$invoice_id")"
printf "   PDF     : %s\n" "$(curl -s -o /tmp/invoice_smoke.pdf -w '%{http_code} %{content_type}' "$base/api/invoices/$invoice_id/pdf")"
printf "   HTML    : %s\n" "$(curl -s -o /dev/null -w '%{http_code} %{content_type}' "$base/api/invoices/$invoice_id/html")"
printf "   bad id  : %s (expected 404)\n" "$(curl -s -o /dev/null -w '%{http_code}' "$base/api/invoices/INV-nope")"
