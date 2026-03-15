#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"

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

now_epoch() { date +%s; }

mtime_epoch() {
  local f="$1"
  if stat -c %Y "$f" > /dev/null 2>&1; then
    stat -c %Y "$f"
    return 0
  fi
  stat -f %m "$f"
}

force=0
quiet=0
ttl_override=""
lock_stale_seconds=180
quick_only=0

while [ $# -gt 0 ]; do
  case "$1" in
    --force) force=1 ;;
    --quiet) quiet=1 ;;
    --ttl=*) ttl_override="${1#--ttl=}" ;;
    --lock-stale-seconds=*) lock_stale_seconds="${1#--lock-stale-seconds=}" ;;
    --quick-only) quick_only=1 ;;
  esac
  shift
done

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
mkdir -p "$cache_dir"

ttl="$(tmux_opt '@pick_session_cache_ttl' '60')"
mutation_ttl="$(tmux_opt '@pick_session_mutation_tombstone_ttl' '300')"
if [ -n "$ttl_override" ]; then
  ttl="$ttl_override"
fi
case "$mutation_ttl" in
  '' | *[!0-9]*) mutation_ttl=300 ;;
esac

if [ "$force" -ne 1 ] && [ -f "$cache_file" ]; then
  mt="$(mtime_epoch "$cache_file" 2> /dev/null || echo 0)"
  age="$(($(now_epoch) - mt))"
  if [ "$age" -ge 0 ] && [ "$age" -lt "$ttl" ]; then
    exit 0
  fi
fi

lock_dir="${cache_file}.lock"
if ! mkdir "$lock_dir" 2> /dev/null; then
  pid_file="${lock_dir}/pid"
  stale=0
  if [ -f "$pid_file" ]; then
    pid="$(cat "$pid_file" 2> /dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2> /dev/null; then
      exit 0
    fi
    stale=1
  else
    mt="$(mtime_epoch "$lock_dir" 2> /dev/null || echo 0)"
    age="$(($(now_epoch) - mt))"
    if [ "$age" -ge "$lock_stale_seconds" ]; then
      stale=1
    fi
  fi
  if [ "$stale" -ne 1 ]; then
    # Another update is already running.
    exit 0
  fi
  rm -rf "$lock_dir" 2> /dev/null || exit 0
  mkdir "$lock_dir" 2> /dev/null || exit 0
fi
cleanup() {
  rm -f "${tmp_quick:-}" "${tmp_full:-}" "${tmp_combined:-}" "${tmp_sessions:-}" 2> /dev/null || true
  rm -f "${lock_dir}/pid" 2> /dev/null || true
  rmdir "$lock_dir" 2> /dev/null || true
}
trap cleanup EXIT
printf '%s\n' "$$" > "${lock_dir}/pid" 2> /dev/null || true

gen="$HOME/.config/tmux/scripts/pick_session/index.sh"
ordered_update_cmd="$HOME/.config/tmux/scripts/pick_session/ordered_cache_update.sh"
if [ ! -x "$gen" ]; then
  exit 0
fi

publish_cache_from() {
  local src="$1"
  local out_tmp
  [ -f "$src" ] || return 1
  out_tmp="$(mktemp -t pick_session_items.XXXXXX)"
  if [ -f "$pending_file" ] || [ -f "$mutation_file" ]; then
    CACHE_FILE="$src" \
      PENDING_FILE="$pending_file" \
      MUTATIONS_FILE="$mutation_file" \
      MUTATION_TTL="$mutation_ttl" \
      CACHE_OUT="$out_tmp" python3 "$script_dir/lib/publish_cache_filter.py"
  else
    cp "$src" "$out_tmp"
  fi
  mv -f "$out_tmp" "$cache_file"
}

file_has_dir_rows() {
  local f="$1"
  [ -f "$f" ] || return 1
  awk -F $'\t' 'NF>=5 && $2 == "dir" { found=1; exit } END { exit(found?0:1) }' "$f" 2> /dev/null
}

file_has_worktree_rows() {
  local f="$1"
  [ -f "$f" ] || return 1
  awk -F $'\t' 'NF>=5 && $2 == "worktree" { found=1; exit } END { exit(found?0:1) }' "$f" 2> /dev/null
}

file_has_non_session_rows() {
  local f="$1"
  [ -f "$f" ] || return 1
  awk -F $'\t' 'NF>=5 && $2 != "session" { found=1; exit } END { exit(found?0:1) }' "$f" 2> /dev/null
}

build_cache_refreshing_sessions_preserving_others() {
  local src="$1"
  local out="$2"

  : > "$out"
  # When src has both sessions and worktrees, preserve its repo-grouped order
  # (sessions and worktrees from the same repo together). Only append dirs from
  # cache. This keeps repo session groups stable with their worktrees
  # worktrees instead of flattening all sessions then all worktrees.
  if file_has_worktree_rows "$src"; then
    awk -F $'\t' 'NF>=5 && ($2 == "session" || $2 == "worktree") { print }' "$src" 2> /dev/null >> "$out" || true
    if file_has_dir_rows "$src"; then
      awk -F $'\t' 'NF>=5 && $2 == "dir" { print }' "$src" 2> /dev/null >> "$out" || true
    elif file_has_dir_rows "$cache_file"; then
      awk -F $'\t' 'NF>=5 && $2 == "dir" { print }' "$cache_file" 2> /dev/null >> "$out" || true
    fi
    awk -F $'\t' 'NF>=5 && $2 != "session" && $2 != "worktree" && $2 != "dir" { print }' "$src" 2> /dev/null >> "$out" || true
    return 0
  fi

  # Fallback: kind-based merge when src has only sessions (e.g. minimal scan).
  awk -F $'\t' 'NF>=5 && $2 == "session" { print }' "$src" 2> /dev/null >> "$out" || true
  if file_has_worktree_rows "$cache_file"; then
    awk -F $'\t' 'NF>=5 && $2 == "worktree" { print }' "$cache_file" 2> /dev/null >> "$out" || true
  else
    awk -F $'\t' 'NF>=5 && $2 == "worktree" { print }' "$src" 2> /dev/null >> "$out" || true
  fi
  if file_has_dir_rows "$cache_file"; then
    awk -F $'\t' 'NF>=5 && $2 == "dir" { print }' "$cache_file" 2> /dev/null >> "$out" || true
  else
    awk -F $'\t' 'NF>=5 && $2 == "dir" { print }' "$src" 2> /dev/null >> "$out" || true
  fi
  if file_has_non_session_rows "$cache_file"; then
    awk -F $'\t' 'NF>=5 && $2 != "session" && $2 != "worktree" && $2 != "dir" { print }' "$cache_file" 2> /dev/null >> "$out" || true
  else
    awk -F $'\t' 'NF>=5 && $2 != "session" && $2 != "worktree" && $2 != "dir" { print }' "$src" 2> /dev/null >> "$out" || true
  fi
}

sanitize_rows() {
  local src="$1"
  local out="$2"
  [ -f "$src" ] || return 1
  awk -F $'\t' 'NF>=5 { print }' "$src" 2> /dev/null > "$out" || true
  [ -s "$out" ]
}

tmp_quick="$(mktemp -t pick_session_items.quick.XXXXXX)"
tmp_full="$(mktemp -t pick_session_items.full.XXXXXX)"
tmp_sessions="$(mktemp -t pick_session_items.sessions.XXXXXX)"
tmp_combined="$(mktemp -t pick_session_items.combined.XXXXXX)"

if [ "$quiet" -ne 1 ] && command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux display-message -d 1500 "pick_session: updating list…" 2> /dev/null || true
fi

quick_ok=0
full_ok=0
quick_published=0
if [ "$quick_only" -eq 1 ]; then
  # Quick refresh: sessions only. We merge into the existing cache to preserve
  # the full worktree/dir lists (quick scans do not discover all worktrees).
  if "$gen" --quick --sessions-only > "$tmp_quick" 2> /dev/null; then
    quick_ok=1
    if [ -s "$tmp_quick" ]; then
      # Always try to merge to preserve worktrees and directories in the cache.
      if [ -f "$cache_file" ]; then
        build_cache_refreshing_sessions_preserving_others "$tmp_quick" "$tmp_combined" || true
        if [ -s "$tmp_combined" ]; then
          publish_cache_from "$tmp_combined" || true
        else
          publish_cache_from "$tmp_quick" || true
        fi
      else
        publish_cache_from "$tmp_quick" || true
      fi
      quick_published=1
    fi
  fi
  if [ "$quick_ok" -ne 1 ] || [ "$quick_published" -ne 1 ]; then
    exit 0
  fi
else
  # Quick scan: sessions only (merged into existing cache).
  "$gen" --quick --sessions-only > "$tmp_quick" 2> /dev/null &
  pid_quick=$!
  # Perform a full scan (including directories) in the background.
  "$gen" > "$tmp_full" 2> /dev/null &
  pid_full=$!

  if wait "$pid_quick"; then
    quick_ok=1
    if [ -s "$tmp_quick" ]; then
      # Merge new sessions into existing cache immediately.
      if [ -f "$cache_file" ]; then
        build_cache_refreshing_sessions_preserving_others "$tmp_quick" "$tmp_combined" || true
        if [ -s "$tmp_combined" ]; then
          publish_cache_from "$tmp_combined" || true
        else
          publish_cache_from "$tmp_quick" || true
        fi
      else
        publish_cache_from "$tmp_quick" || true
      fi
      quick_published=1
    fi
  fi

  # Stream progressively-complete snapshots from the full scan into cache while
  # index generation is still running. This keeps picker refresh responsive:
  # fzf always reads the latest cache snapshot without waiting for scan end.
  last_stream_size=-1
  while kill -0 "$pid_full" 2> /dev/null; do
    if [ -s "$tmp_full" ]; then
      cur_size="$(wc -c < "$tmp_full" 2> /dev/null || echo 0)"
      case "$cur_size" in
        '' | *[!0-9]*) cur_size=0 ;;
      esac
      if [ "$cur_size" -gt 0 ] && [ "$cur_size" -ne "$last_stream_size" ]; then
        if sanitize_rows "$tmp_full" "$tmp_sessions"; then
          # Merge partial full-scan rows with current cache so in-flight
          # results do not drop already-known dirs/worktrees/sessions.
          if [ -f "$cache_file" ]; then
            build_cache_refreshing_sessions_preserving_others "$tmp_sessions" "$tmp_combined" || true
            if [ -s "$tmp_combined" ]; then
              publish_cache_from "$tmp_combined" || true
            else
              publish_cache_from "$tmp_sessions" || true
            fi
          else
            publish_cache_from "$tmp_sessions" || true
          fi
          quick_published=1
        fi
        last_stream_size="$cur_size"
      fi
    fi
    sleep 0.2
  done

  if wait "$pid_full"; then
    full_ok=1
    if sanitize_rows "$tmp_full" "$tmp_sessions"; then
      publish_cache_from "$tmp_sessions" || true
    elif [ "$quick_published" -eq 0 ] && [ "$quick_ok" -eq 1 ] && [ -s "$tmp_quick" ]; then
      publish_cache_from "$tmp_quick" || true
    fi
  fi

  if [ "$full_ok" -ne 1 ] && [ "$quick_ok" -eq 1 ] && [ "$quick_published" -eq 0 ] && [ -s "$tmp_quick" ]; then
    publish_cache_from "$tmp_quick" || true
    quick_published=1
  fi

  if [ "$full_ok" -ne 1 ] && [ "$quick_ok" -ne 1 ]; then
    exit 0
  fi
fi

if [ "$quiet" -ne 1 ] && command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux display-message -d 1500 "pick_session: list updated" 2> /dev/null || true
fi

# Keep a precomputed ordered snapshot in sync so picker open can stay instant.
if [ -x "$ordered_update_cmd" ] && [ -s "$cache_file" ]; then
  "$ordered_update_cmd" --quiet > /dev/null 2>&1 &
fi
