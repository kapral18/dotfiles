#!/usr/bin/env bash
# Toggle work/home mode for the GitHub picker.
# Called by fzf's transform binding. Outputs fzf actions to stdout.
set -euo pipefail

mode_file="${1:-}"
items_cmd="${2:-}"
scope_file="${3:-}"

[ -n "$mode_file" ] || exit 1
[ -n "$items_cmd" ] || exit 1

cur="$(cat "$mode_file" 2> /dev/null || echo work)"
scope="all"
if [ -n "$scope_file" ]; then
  scope="$(cat "$scope_file" 2> /dev/null || echo all)"
fi
if [ "$cur" = "work" ]; then
  next="home"
else
  next="work"
fi

printf '%s' "$next" > "$mode_file"
printf 'reload(GH_PICKER_MODE=%s GH_PICKER_SCOPE=%s %s)+change-prompt(  %s/%s  )' "$next" "$scope" "$items_cmd" "$next" "$scope"
printf '+clear-query'
