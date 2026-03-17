#!/usr/bin/env bash
set -euo pipefail

kind="${1:-}"
repo="${2:-}"
num="${3:-}"

if [ -z "$kind" ] || [ -z "$repo" ] || [ -z "$num" ]; then
  cat
  exit 0
fi

match="$(mktemp -t gh_pin_match.XXXXXX)"
rest="$(mktemp -t gh_pin_rest.XXXXXX)"
cleanup() { rm -f "$match" "$rest" 2> /dev/null || true; }
trap cleanup EXIT

awk -F $'\t' -v k="$kind" -v r="$repo" -v n="$num" -v mf="$match" -v rf="$rest" '
  NF < 5 { print > rf; next }
  ($2 == k && $3 == r && $4 == n) { print > mf; next }
  { print > rf }
'

cat "$match" "$rest"
