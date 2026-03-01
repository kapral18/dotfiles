#!/usr/bin/env bash
set -euo pipefail

if ! command -v tmux >/dev/null 2>&1; then
  exit 0
fi

bulk_guard_key="@pick_session_bulk_create_in_progress"
bulk_guard="$(tmux show-option -gqv "$bulk_guard_key" 2>/dev/null || true)"
case "$bulk_guard" in
1 | true | yes | on)
  # The picker will trigger a single refresh after bulk operations.
  exit 0
  ;;
esac

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
mkdir -p "$cache_dir" 2>/dev/null || true
lock_dir="${cache_dir}/pick_session_index_update_hook.lock"

# Coalesce bursts of new-session/rename-session events into one refresh.
if ! mkdir "$lock_dir" 2>/dev/null; then
  exit 0
fi
cleanup() { rmdir "$lock_dir" 2>/dev/null || true; }
trap cleanup EXIT

# Let multiple events arrive before refreshing.
sleep 0.4

exec "$HOME/.config/tmux/scripts/pick_session_index_update.sh" --force --quiet --quick-only
