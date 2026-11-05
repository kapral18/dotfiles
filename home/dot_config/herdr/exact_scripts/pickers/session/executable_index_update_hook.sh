#!/usr/bin/env bash
# herdr plugin hook for workspace.created / workspace.renamed: refresh the
# session picker cache unless a picker is open (it refreshes once on exit).
set -euo pipefail

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/herdr-pickers"
mkdir -p "$cache_dir" 2> /dev/null || true

for guard in "$cache_dir"/pick_session_bulk_create.*; do
  [ -e "$guard" ] || continue
  if kill -0 "${guard##*.}" 2> /dev/null; then
    exit 0
  fi
  rm -f "$guard"
done

lock_dir="${cache_dir}/pick_session_index_update_hook.lock"

# Coalesce bursts of workspace events into one refresh.
if ! mkdir "$lock_dir" 2> /dev/null; then
  exit 0
fi
cleanup() { rmdir "$lock_dir" 2> /dev/null || true; }
trap cleanup EXIT

# Let multiple events arrive before refreshing.
sleep 0.4

"$HOME/.config/herdr/scripts/pickers/session/index_update.sh" --force --quiet --quick-only --defer-if-busy
