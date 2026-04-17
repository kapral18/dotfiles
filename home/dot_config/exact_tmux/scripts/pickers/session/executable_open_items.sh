#!/usr/bin/env bash
set -euo pipefail

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
ordered_file="${cache_dir}/pick_session_items_ordered.tsv"
cache_file="${cache_dir}/pick_session_items.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"
items_cmd="$HOME/.config/tmux/scripts/pickers/session/items.sh"
ordered_update_cmd="$HOME/.config/tmux/scripts/pickers/session/ordered_cache_update.sh"
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

  # Cache the "current-markered" ordered snapshot so repeated opens are instant.
  # Recompute only when the active session changes or the ordered snapshot mtime changes.
  local fixed_file="${cache_dir}/pick_session_items_ordered.current.tsv"
  local meta_file="${fixed_file}.meta"
  local src_mtime=""
  src_mtime="$(stat -f %m "$file" 2> /dev/null || true)"
  local src_size=""
  src_size="$(stat -f %z "$file" 2> /dev/null || true)"

  if [ -n "$src_mtime" ] && [ -n "$src_size" ] && [ -s "$fixed_file" ] && [ -s "$meta_file" ]; then
    local meta_cur="" meta_mtime="" meta_size=""
    meta_cur="$(awk 'NR==1{print; exit}' "$meta_file" 2> /dev/null || true)"
    meta_mtime="$(awk 'NR==2{print; exit}' "$meta_file" 2> /dev/null || true)"
    meta_size="$(awk 'NR==3{print; exit}' "$meta_file" 2> /dev/null || true)"
    if [ "$meta_cur" = "$cur" ] && [ "$meta_mtime" = "$src_mtime" ] && [ "$meta_size" = "$src_size" ]; then
      cat "$fixed_file"
      return
    fi
  fi

  local tmp_fixed="" tmp_meta=""
  tmp_fixed="$(mktemp -t pick_session_items_ordered_current.XXXXXX 2> /dev/null || printf '%s\n' "/tmp/pick_session_items_ordered_current.$$")"
  tmp_meta="$(mktemp -t pick_session_items_ordered_current_meta.XXXXXX 2> /dev/null || printf '%s\n' "/tmp/pick_session_items_ordered_current_meta.$$")"

  if CURRENT="$cur" python3 -u "$script_dir/lib/fixup_current_marker.py" "$file" > "$tmp_fixed"; then
    printf '%s\n%s\n%s\n' "$cur" "$src_mtime" "$src_size" > "$tmp_meta" 2> /dev/null || true
    mv -f "$tmp_fixed" "$fixed_file" 2> /dev/null || cat "$tmp_fixed" > "$fixed_file" 2> /dev/null || true
    mv -f "$tmp_meta" "$meta_file" 2> /dev/null || cat "$tmp_meta" > "$meta_file" 2> /dev/null || true
    cat "$fixed_file"
  else
    rm -f "$tmp_fixed" "$tmp_meta" 2> /dev/null || true
    CURRENT="$cur" python3 -u "$script_dir/lib/fixup_current_marker.py" "$file"
  fi
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
  # If the underlying cache changed, treat the ordered snapshot as stale so we
  # don't reopen with an out-of-date list (e.g. after ctrl-r refresh).
  [ -s "$cache_file" ] && [ "$cache_file" -nt "$ordered_file" ] && stale=1
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
