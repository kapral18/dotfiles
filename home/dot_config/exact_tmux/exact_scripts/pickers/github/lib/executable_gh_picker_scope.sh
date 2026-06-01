#!/usr/bin/env bash
# Switch the GitHub picker dashboard scope.
# Called by fzf transform bindings. Outputs fzf actions to stdout.
set -euo pipefail

mode_file="${1:-}"
scope_file="${2:-}"
items_cmd="${3:-}"
next="${4:-}"

[ -n "$mode_file" ] || exit 1
[ -n "$scope_file" ] || exit 1
[ -n "$items_cmd" ] || exit 1
[ -n "$next" ] || exit 1

mode="$(cat "$mode_file" 2> /dev/null || echo work)"
printf '%s' "$next" > "$scope_file"

printf 'reload(GH_PICKER_MODE=%s GH_PICKER_SCOPE=%s %s --cache-only 2>/dev/null)+change-prompt(  %s/%s  )' \
  "$mode" \
  "$next" \
  "$items_cmd" \
  "$mode" \
  "$next"
printf '+clear-query'
