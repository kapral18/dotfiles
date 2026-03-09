#!/usr/bin/env bash
set -euo pipefail

mtime_epoch() {
  local f="$1"
  [ -f "$f" ] || {
    printf '0\n'
    return 0
  }
  if stat -c %Y "$f" >/dev/null 2>&1; then
    stat -c %Y "$f"
    return 0
  fi
  stat -f %m "$f"
}

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
ordered_file="${cache_dir}/pick_session_items_ordered.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"
items_cmd="$HOME/.config/tmux/scripts/pick_session_items.sh"
ordered_update_cmd="$HOME/.config/tmux/scripts/pick_session_ordered_cache_update.sh"

cache_mt="$(mtime_epoch "$cache_file" 2>/dev/null || printf '0')"
ordered_mt="$(mtime_epoch "$ordered_file" 2>/dev/null || printf '0')"
mutation_mt="$(mtime_epoch "$mutation_file" 2>/dev/null || printf '0')"
pending_mt="$(mtime_epoch "$pending_file" 2>/dev/null || printf '0')"

if [ -s "$ordered_file" ] && [ "$ordered_mt" -ge "$cache_mt" ] && [ "$ordered_mt" -ge "$mutation_mt" ] && [ "$ordered_mt" -ge "$pending_mt" ]; then
  cat "$ordered_file"
  exit 0
fi

if [ -x "$ordered_update_cmd" ] && [ -s "$cache_file" ]; then
  "$ordered_update_cmd" --quiet >/dev/null 2>&1 &
fi

if [ -x "$items_cmd" ]; then
  exec "$items_cmd"
fi

[ -f "$cache_file" ] && cat "$cache_file"
