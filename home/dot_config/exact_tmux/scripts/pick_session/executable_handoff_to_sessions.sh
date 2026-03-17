#!/usr/bin/env bash
set -euo pipefail

kind="${1:-}" # pr|issue
repo="${2:-}" # owner/name
num="${3:-}"
out_file="${4:-}"

[ -n "$out_file" ] || exit 0

printf '%s\t%s\t%s\n' "$kind" "$repo" "$num" > "$out_file" 2> /dev/null || true
