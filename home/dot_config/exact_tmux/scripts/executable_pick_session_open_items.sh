#!/usr/bin/env bash
set -euo pipefail

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
ordered_file="${cache_dir}/pick_session_items_ordered.tsv"
cache_file="${cache_dir}/pick_session_items.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"
items_cmd="$HOME/.config/tmux/scripts/pick_session_items.sh"
ordered_update_cmd="$HOME/.config/tmux/scripts/pick_session_ordered_cache_update.sh"

# Fast path: precomputed ordered snapshot exists and is not invalidated by
# recent mutations (ctrl-x kill / alt-x remove) or pending items.
if [ -s "$ordered_file" ]; then
  stale=0
  [ -s "$mutation_file" ] && [ "$mutation_file" -nt "$ordered_file" ] && stale=1
  [ -s "$pending_file" ] && [ "$pending_file" -nt "$ordered_file" ] && stale=1
  if [ "$stale" -eq 0 ]; then
    exec cat "$ordered_file"
  fi
fi

# Ordered file missing or stale — items_cmd handles mutation tombstones
# internally, so prefer it over serving the raw cache.
if [ -x "$items_cmd" ]; then
  [ -x "$ordered_update_cmd" ] && "$ordered_update_cmd" --quiet >/dev/null 2>&1 &
  exec "$items_cmd"
fi

[ -f "$cache_file" ] && exec cat "$cache_file"
