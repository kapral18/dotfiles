#!/usr/bin/env bash
set -euo pipefail

need_cmd() {
  command -v "$1" > /dev/null 2>&1
}

tmux_opt() {
  local key="$1"
  local default_value="$2"
  local value=""
  if command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
    value="$(tmux show-option -gqv "${key}" 2> /dev/null || true)"
  fi
  if [ -n "$value" ]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$default_value"
  fi
}

items_cmd="$HOME/.config/tmux/scripts/pickers/session/items.sh"
update_cmd="$HOME/.config/tmux/scripts/pickers/session/index_update.sh"

refresh=0
force_order=0
force_refresh=0
for arg in "$@"; do
  case "$arg" in
    --refresh) refresh=1 ;;
    --force-order) force_order=1 ;;
    --force-refresh) force_refresh=1 ;;
  esac
done

if [ "$force_refresh" -eq 1 ] && [ -x "$update_cmd" ]; then
  "$update_cmd" --force --quiet --quick-only > /dev/null 2>&1 || true
  "$update_cmd" --force --quiet > /dev/null 2>&1 || true
elif [ "$refresh" -eq 1 ] && [ -x "$update_cmd" ]; then
  (
    "$update_cmd" --force --quiet --quick-only > /dev/null 2>&1 || true
    "$update_cmd" --force --quiet > /dev/null 2>&1 || true
  ) > /dev/null 2>&1 &
fi

if [ ! -x "$items_cmd" ]; then
  cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
  cache_file="${cache_dir}/pick_session_items.tsv"
  [ -f "$cache_file" ] && cat "$cache_file"
  exit 0
fi

if ! need_cmd python3; then
  exec "$items_cmd"
fi

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
passthrough_rows_default="${PICK_SESSION_FILTER_PASSTHROUGH_ROWS:-2000}"
passthrough_rows="$(tmux_opt '@pick_session_filter_passthrough_rows' "$passthrough_rows_default")"
case "$passthrough_rows" in
  '' | *[!0-9]*) passthrough_rows=2000 ;;
esac

# Keep open latency flat for very large lists by skipping expensive regrouping.
if [ "$force_order" -ne 1 ] && [ "$passthrough_rows" -gt 0 ] && [ -f "$cache_file" ]; then
  cache_rows="$(wc -l < "$cache_file" 2> /dev/null || echo 0)"
  case "$cache_rows" in
    '' | *[!0-9]*) cache_rows=0 ;;
  esac
  if [ "$cache_rows" -ge "$passthrough_rows" ]; then
    exec "$items_cmd"
  fi
fi

scan_roots_raw=""
scan_roots_raw="$(tmux_opt '@pick_session_worktree_scan_roots' '')"
if [ -z "${scan_roots_raw:-}" ]; then
  scan_roots_raw="$HOME/work,$HOME/code,$HOME/.backport/repositories,$HOME/.local/share"
fi

script_dir="$(cd "$(dirname "$0")" && pwd)"

ITEMS_CMD="$items_cmd" PICK_SESSION_SCAN_ROOTS="$scan_roots_raw" PICK_SESSION_FILTER_PASSTHROUGH_ROWS="$passthrough_rows" PICK_SESSION_FILTER_FORCE_ORDER="$force_order" PYTHONPATH="$script_dir/lib:${PYTHONPATH:-}" python3 -u "$script_dir/lib/filter_main.py"
