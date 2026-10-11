#!/usr/bin/env bash
# Switch the GitHub picker dashboard scope.
# Called by fzf transform bindings. Outputs fzf actions to stdout.
set -euo pipefail

scope_file="${1:-}"
items_cmd="${2:-}"
next="${3:-}"

[ -n "$scope_file" ] || exit 1
[ -n "$items_cmd" ] || exit 1
[ -n "$next" ] || exit 1

printf '%s' "$next" > "$scope_file"

printf 'reload(GH_PICKER_SCOPE=%s %s --cache-only 2>/dev/null)+change-prompt(  %s  )' \
  "$next" \
  "$items_cmd" \
  "$next"
printf '+clear-query'
