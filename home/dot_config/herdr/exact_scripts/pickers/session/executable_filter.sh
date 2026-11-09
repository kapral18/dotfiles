#!/usr/bin/env bash
set -euo pipefail

need_cmd() {
  command -v "$1" > /dev/null 2>&1
}

# shellcheck source=../lib/herdr_ws.sh
. "$HOME/.config/herdr/scripts/pickers/lib/herdr_ws.sh"

items_cmd="$HOME/.config/herdr/scripts/pickers/session/items.sh"
update_cmd="$HOME/.config/herdr/scripts/pickers/session/index_update.sh"

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
  # alt-r: full synchronous refresh; blocks until quick and full scans both
  # complete so the picker reload sees the freshest possible state.
  "$update_cmd" --force --quiet --quick-only --skip-dirty > /dev/null 2>&1 || true
  "$update_cmd" --force --quiet > /dev/null 2>&1 || true
elif [ "$refresh" -eq 1 ] && [ -x "$update_cmd" ]; then
  # ctrl-r: synchronous quick scan (sessions only) so the picker reload that
  # follows this filter call sees up-to-date session rows on the first try.
  # Dirty badges are preserved from the existing cache here and recomputed by
  # the background full scan. Exact dirty checks across many large worktrees can
  # dominate ctrl-r latency, while session membership itself is cheap to verify.
  "$update_cmd" --force --quiet --quick-only --skip-dirty > /dev/null 2>&1 || true
  # Background chain: first a fast full scan (--skip-dirty --skip-gh: discovery
  # + emission only, badges hydrated from existing caches, ~15s) so brand-new
  # worktrees/dirs reach the cache (and the open picker, via live_refresh)
  # shortly after ctrl-r; then the real full scan for fresh dirty/gh badges.
  # The slow scan alone takes minutes and is pre-empted by any later --force
  # update, so without the fast pass new dirs could stay invisible for days.
  bg_chain="$(printf '%q' "$update_cmd") --force --quiet --skip-dirty --skip-gh; PICK_SESSION_THREADS=1 $(printf '%q' "$update_cmd") --force --quiet"
  if [ -n "${HERDR_SOCKET_PATH:-}" ]; then
    "$HOME/lib/shared/detach.sh" bash -c "$bg_chain" < /dev/null > /dev/null 2>&1 &
  else
    "$HOME/lib/shared/detach.sh" sh -c "$bg_chain" < /dev/null > /dev/null 2>&1 &
  fi
fi

if [ ! -x "$items_cmd" ]; then
  cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/herdr-pickers"
  cache_file="${cache_dir}/pick_session_items.tsv"
  [ -f "$cache_file" ] && cat "$cache_file"
  exit 0
fi

if ! need_cmd python3; then
  exec "$items_cmd"
fi

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/herdr-pickers"
cache_file="${cache_dir}/pick_session_items.tsv"
passthrough_rows_default="${PICK_SESSION_FILTER_PASSTHROUGH_ROWS:-2000}"
passthrough_rows="$(picker_opt '@pick_session_filter_passthrough_rows' "$passthrough_rows_default")"
case "$passthrough_rows" in
  '' | *[!0-9]*) passthrough_rows=2000 ;;
esac

# Keep open latency flat for very large lists by skipping expensive regrouping.
# An active alt-o filter must run through grouping, so it bypasses the
# passthrough escape (like --force-order).
only_active=0
[ -s "${PICK_SESSION_ONLY_FILE:-}" ] && only_active=1
if [ "$only_active" -eq 0 ] && [ "$force_order" -ne 1 ] && [ "$passthrough_rows" -gt 0 ] && [ -f "$cache_file" ]; then
  cache_rows="$(wc -l < "$cache_file" 2> /dev/null || echo 0)"
  case "$cache_rows" in
    '' | *[!0-9]*) cache_rows=0 ;;
  esac
  if [ "$cache_rows" -ge "$passthrough_rows" ]; then
    exec "$items_cmd"
  fi
fi

scan_roots_raw=""
scan_roots_raw="$(picker_opt '@pick_session_worktree_scan_roots' '')"
if [ -z "${scan_roots_raw:-}" ]; then
  scan_roots_raw="$HOME/code,$HOME/.local/share"
fi

script_dir="$(cd "$(dirname "$0")" && pwd)"

ITEMS_CMD="$items_cmd" PICK_SESSION_SCAN_ROOTS="$scan_roots_raw" PICK_SESSION_FILTER_PASSTHROUGH_ROWS="$passthrough_rows" PICK_SESSION_FILTER_FORCE_ORDER="$force_order" PYTHONPATH="$script_dir/lib:${PYTHONPATH:-}" python3 -u "$script_dir/lib/filter_main.py"
