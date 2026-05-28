#!/usr/bin/env bash
# Cycle the GitHub picker sort key and reload the cache.
# Called by the alt-S fzf transform binding; outputs fzf actions.
#
# Args: <mode_file> <scope_file> <items_cmd>
#
# Sort cycle: created-desc -> updated-desc -> age-asc -> repo-asc -> back.
# State persisted at ~/.cache/tmux/gh_picker_sort; consumed by
# `gh_items_main.py` when filtering and re-sorting cache lines for emit.
set -euo pipefail

mode_file="${1:-}"
scope_file="${2:-}"
items_cmd="${3:-}"

if [ -z "$mode_file" ] || [ -z "$scope_file" ] || [ -z "$items_cmd" ]; then
  exit 0
fi

mode="$(cat "$mode_file" 2> /dev/null || echo work)"
scope="$(cat "$scope_file" 2> /dev/null || echo all)"
cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
sort_file="${cache_dir}/gh_picker_sort"
mkdir -p "$cache_dir" 2> /dev/null || true

current="$(cat "$sort_file" 2> /dev/null || echo created-desc)"
case "$current" in
  created-desc) next="updated-desc" ;;
  updated-desc) next="age-asc" ;;
  age-asc) next="repo-asc" ;;
  repo-asc) next="created-desc" ;;
  *) next="created-desc" ;;
esac

printf '%s' "$next" > "$sort_file"

# Toast the new sort first, then reload. execute-silent runs in foreground
# but tmux display-message returns instantly, so the reload follows promptly.
printf 'execute-silent(tmux display-message "gh-picker sort: %s" 2>/dev/null || true)+reload(GH_PICKER_MODE=%s GH_PICKER_SCOPE=%s %s --cache-only)' \
  "$next" "$mode" "$scope" "$items_cmd"
