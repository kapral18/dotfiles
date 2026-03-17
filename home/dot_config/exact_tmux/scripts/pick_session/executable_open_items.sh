#!/usr/bin/env bash
set -euo pipefail

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
ordered_file="${cache_dir}/pick_session_items_ordered.tsv"
cache_file="${cache_dir}/pick_session_items.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"
items_cmd="$HOME/.config/tmux/scripts/pick_session/items.sh"
ordered_update_cmd="$HOME/.config/tmux/scripts/pick_session/ordered_cache_update.sh"
script_dir="$(cd "$(dirname "$0")" && pwd)"

# The (current) marker is baked into cached/ordered output at generation time.
# Dynamically fix it up so it always reflects the *active* session.
fixup_current_marker() {
  local file="$1"
  local cur=""
  if [ -n "${TMUX:-}" ]; then
    cur="$(tmux display-message -p '#S' 2> /dev/null || true)"
  fi
  if [ -z "$cur" ]; then
    cat "$file"
    return
  fi
  CURRENT="$cur" python3 -u "$script_dir/lib/fixup_current_marker.py" "$file"
}

ordered_has_session_rows() {
  local f="$1"
  [ -f "$f" ] || return 1
  awk -F $'\t' 'NF >= 2 && $2 == "session" { found=1; exit } END { exit(found?0:1) }' "$f" 2> /dev/null
}

# Fast path: precomputed ordered snapshot exists and is not invalidated by
# recent mutations (ctrl-x kill / alt-x remove) or pending items.
if [ -s "$ordered_file" ]; then
  stale=0
  # If the underlying cache changed, regenerate ordering only when the ordered
  # snapshot is missing session rows (otherwise keep the fast ordered path).
  if [ -s "$cache_file" ] && [ "$cache_file" -nt "$ordered_file" ]; then
    ordered_has_session_rows "$ordered_file" || stale=1
  fi
  [ -s "$mutation_file" ] && [ "$mutation_file" -nt "$ordered_file" ] && stale=1
  [ -s "$pending_file" ] && [ "$pending_file" -nt "$ordered_file" ] && stale=1
  if [ "$stale" -eq 0 ]; then
    fixup_current_marker "$ordered_file"
    exit 0
  fi
fi

# Ordered file missing or stale — items_cmd handles mutation tombstones
# internally, so prefer it over serving the raw cache.
if [ -x "$items_cmd" ]; then
  [ -x "$ordered_update_cmd" ] && "$ordered_update_cmd" --quiet > /dev/null 2>&1 &
  exec "$items_cmd"
fi

[ -f "$cache_file" ] && exec cat "$cache_file"
