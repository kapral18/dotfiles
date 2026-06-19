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
skip_dirty=0
skip_gh=0

while [ $# -gt 0 ]; do
  case "$1" in
    --force) force=1 ;;
    --quiet) quiet=1 ;;
    --ttl=*) ttl_override="${1#--ttl=}" ;;
    --lock-stale-seconds=*) lock_stale_seconds="${1#--lock-stale-seconds=}" ;;
    --quick-only) quick_only=1 ;;
    --skip-dirty) skip_dirty=1 ;;
    --skip-gh) skip_gh=1 ;;
  esac
  shift
done

gh_cache_needs_author_refresh() {
  [ "$skip_gh" -eq 0 ] || return 1
  [ -x "$script_dir/lib/index_main.py" ] || return 1
  command -v python3 > /dev/null 2>&1 || return 1
  python3 "$script_dir/lib/index_main.py" --gh-cache-needs-author-refresh > /dev/null 2>&1
}

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
error_log="${cache_dir}/pick_session_index_error.log"
full_scan_stamp="${cache_dir}/pick_session_full_scan.stamp"
mkdir -p "$cache_dir"

notify_error() {
  local phase="$1"
  local log="$2"
  local msg="pick_session index ${phase} failed"
  if [ -s "$log" ]; then
    local last_line
    last_line="$(tail -1 "$log" 2> /dev/null || true)"
    if [ -n "$last_line" ]; then
      msg="${msg}: ${last_line}"
    fi
  fi
  if command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
    tmux display-message -d 5000 "$msg" 2> /dev/null || true
  fi
  printf '%s [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$$" "$msg" >> "$error_log" 2> /dev/null || true
}

ttl="$(tmux_opt '@pick_session_cache_ttl' '60')"
# Full scans (worktree/dir discovery) are gated on their own freshness stamp,
# independent of the cache mtime, so that frequent quick-only refreshes (which
# bump the cache mtime on every session switch/create/picker open) cannot
# starve the full scan. Without this, the full scan -- the only path that finds
# session-less worktrees -- was perpetually skipped whenever a quick refresh had
# touched the cache within `ttl`, so the picker only ever listed worktrees that
# happened to have a live tmux session.
full_scan_ttl="$(tmux_opt '@pick_session_full_scan_ttl' '60')"
mutation_ttl="$(tmux_opt '@pick_session_mutation_tombstone_ttl' '300')"
if [ -n "$ttl_override" ]; then
  ttl="$ttl_override"
  # An explicit --ttl override (e.g. the live-refresh loop's --ttl=20) governs
  # the quick cadence; the full scan keeps its own, longer cadence so the live
  # loop can repaint sessions often without re-running the expensive full scan
  # on every tick. Callers wanting a forced full scan use --force.
fi
case "$mutation_ttl" in
  '' | *[!0-9]*) mutation_ttl=300 ;;
esac
case "$full_scan_ttl" in
  '' | *[!0-9]*) full_scan_ttl=60 ;;
esac

needs_author_refresh=0
if [ "$quick_only" -ne 1 ] && gh_cache_needs_author_refresh; then
  needs_author_refresh=1
fi

if [ "$force" -ne 1 ] && [ "$needs_author_refresh" -ne 1 ]; then
  if [ "$quick_only" -eq 1 ]; then
    # Quick-only: gate on cache mtime (cheap, session-focused refresh).
    if [ -f "$cache_file" ]; then
      mt="$(mtime_epoch "$cache_file" 2> /dev/null || echo 0)"
      age="$(($(now_epoch) - mt))"
      if [ "$age" -ge 0 ] && [ "$age" -lt "$ttl" ]; then
        exit 0
      fi
    fi
  else
    # Full scan: gate on the dedicated full-scan stamp so quick refreshes that
    # bumped the cache mtime do not reset this window.
    if [ -f "$full_scan_stamp" ]; then
      mt="$(mtime_epoch "$full_scan_stamp" 2> /dev/null || echo 0)"
      age="$(($(now_epoch) - mt))"
      if [ "$age" -ge 0 ] && [ "$age" -lt "$full_scan_ttl" ]; then
        exit 0
      fi
    fi
  fi
fi

lock_dir="${cache_file}.lock"
pid_file="${lock_dir}/pid"
# Manual --force invocations (alt-r, ctrl-r) pre-empt an in-flight updater
# (typically a live_refresh tick) so they aren't silently no-op'd. Without
# pre-emption the manual refresh would defer to the live tick and the user
# would see stale rows after their explicit refresh. Pattern mirrors the
# refresh pre-emption in pickers/github/gh_items.sh.
while ! mkdir "$lock_dir" 2> /dev/null; do
  pid=""
  [ -f "$pid_file" ] && pid="$(cat "$pid_file" 2> /dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2> /dev/null; then
    if [ "$force" -eq 1 ]; then
      kill "$pid" 2> /dev/null || true
      waited=0
      while kill -0 "$pid" 2> /dev/null && [ "$waited" -lt 30 ]; do
        sleep 0.1
        waited="$((waited + 1))"
      done
      if kill -0 "$pid" 2> /dev/null; then
        kill -KILL "$pid" 2> /dev/null || true
        sleep 0.1
      fi
      rm -rf "$lock_dir" 2> /dev/null || true
      continue
    fi
    # Another updater is in flight and this is not a manual refresh; defer.
    exit 0
  fi
  # No live owner: either lock_dir is a leftover from a crashed updater
  # (no pid file) past the stale window, or pid file points at a dead pid.
  if [ ! -f "$pid_file" ]; then
    mt="$(mtime_epoch "$lock_dir" 2> /dev/null || echo 0)"
    age="$(($(now_epoch) - mt))"
    if [ "$age" -lt "$lock_stale_seconds" ]; then
      # Race: another updater is mid-startup (mkdir'd but hasn't written pid
      # yet). Defer rather than steal.
      exit 0
    fi
  fi
  rm -rf "$lock_dir" 2> /dev/null || exit 0
done
gen_pids=()
cleanup() {
  # Take any in-flight `gen` children with us so they don't keep running and
  # racing the successor's writes. pkill -TERM -P also catches their python
  # grandchildren (gen is a thin bash wrapper around python3 index_main.py).
  local _p
  for _p in ${gen_pids[@]+"${gen_pids[@]}"}; do
    [ -n "$_p" ] || continue
    if kill -0 "$_p" 2> /dev/null; then
      pkill -TERM -P "$_p" 2> /dev/null || true
      kill -TERM "$_p" 2> /dev/null || true
    fi
  done
  rm -f "${tmp_quick:-}" "${tmp_full:-}" "${tmp_combined:-}" "${tmp_sessions:-}" "${tmp_err_quick:-}" "${tmp_err_full:-}" 2> /dev/null || true
  # Ownership-checked release: if we've been pre-empted by a successor that
  # already wrote its own $$ into pid_file, do not unlink their lock.
  if [ -d "$lock_dir" ]; then
    local _cur_pid
    _cur_pid="$(cat "$pid_file" 2> /dev/null || true)"
    if [ "$_cur_pid" = "$$" ]; then
      rm -f "$pid_file" 2> /dev/null || true
      rmdir "$lock_dir" 2> /dev/null || true
    fi
  fi
}
# TERM/HUP from a pre-empting successor must exit promptly so cleanup runs
# (and the successor can take the lock). We exit 0 (not 143) so that
# `tmux run-shell -b` invocations of this script do not surface a visible
# "returned 143" error in the UI for expected pre-emptions (e.g. rapid
# ctrl-r or alt-r). The `wait` on `gen` children can still see rc=143 from
# pkill during our own cleanup, but the post-wait notify paths are bypassed
# by the forced exit before we reach them.
trap 'exit 0' TERM HUP
trap 'exit 130' INT
trap cleanup EXIT
printf '%s\n' "$$" > "${lock_dir}/pid" 2> /dev/null || true

gen="$HOME/.config/tmux/scripts/pickers/session/index.sh"
ordered_update_cmd="$HOME/.config/tmux/scripts/pickers/session/ordered_cache_update.sh"
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
  if [ -f "$cache_file" ] && cmp -s "$out_tmp" "$cache_file"; then
    rm -f "$out_tmp"
  else
    mv -f "$out_tmp" "$cache_file"
  fi
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

# Union cached worktree rows into an in-flight (partial) full-scan snapshot.
#
# The full scan emits per repo group as `sessions...` then `worktrees...`. A
# partial snapshot read mid-stream can therefore contain a repo's sessions but
# be truncated *before* that repo's worktree rows. Publishing such a partial
# verbatim drops those worktrees from the cache; if the scan is then killed
# (e.g. tmux server kill during session restore) the truncation persists. This
# is exactly the failure mode where the picker showed only the ~/work/kibana/*
# worktrees that happened to have a live session.
#
# To make partial publishes monotonic for worktrees, re-append any cached
# worktree row whose path is not already represented (as session or worktree)
# in the partial. Dedup downstream (pick_session_grouping.dedup_best) collapses
# duplicates and prefers session > worktree, so this can only add missing
# worktrees, never reorder or duplicate visibly. The authoritative full publish
# (after a successful scan) still replaces the cache wholesale.
union_cached_worktrees_into_partial() {
  local partial="$1"
  [ -f "$partial" ] || return 0
  file_has_worktree_rows "$cache_file" || return 0
  awk -F $'\t' '
    FNR == NR {
      if (NF >= 5 && ($2 == "session" || $2 == "worktree")) seen[$3] = 1
      next
    }
    NF >= 5 && $2 == "worktree" && !($3 in seen) { print }
  ' "$partial" "$cache_file" >> "$partial" 2> /dev/null || true
}

tmp_quick="$(mktemp -t pick_session_items.quick.XXXXXX)"
tmp_full="$(mktemp -t pick_session_items.full.XXXXXX)"
tmp_sessions="$(mktemp -t pick_session_items.sessions.XXXXXX)"
tmp_combined="$(mktemp -t pick_session_items.combined.XXXXXX)"
tmp_err_quick="$(mktemp -t pick_session_err.quick.XXXXXX)"
tmp_err_full="$(mktemp -t pick_session_err.full.XXXXXX)"

if [ "$quiet" -ne 1 ] && command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux display-message -d 1500 "pick_session: updating list…" 2> /dev/null || true
fi

quick_ok=0
full_ok=0
quick_published=0
if [ "$quick_only" -eq 1 ]; then
  # Quick refresh: sessions only. We merge into the existing cache to preserve
  # the full worktree/dir lists (quick scans do not discover all worktrees).
  # Run gen in the background and `wait` so TERM/HUP from a pre-empting
  # successor can interrupt us (foreground children defer signal delivery
  # until they exit — see cleanup() docstring for why this matters).
  gen_quick_args=(--quick --sessions-only)
  [ "$skip_dirty" -eq 1 ] && gen_quick_args+=(--skip-dirty)
  "$gen" "${gen_quick_args[@]}" > "$tmp_quick" 2> "$tmp_err_quick" &
  pid_quick=$!
  gen_pids+=("$pid_quick")
  set +e
  wait "$pid_quick"
  gen_rc=$?
  set -e
  if [ "$gen_rc" -eq 0 ]; then
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
  else
    notify_error "quick scan" "$tmp_err_quick"
  fi
  if [ "$quick_ok" -ne 1 ] || [ "$quick_published" -ne 1 ]; then
    exit 0
  fi
else
  # Quick scan: sessions only (merged into existing cache).
  gen_skip_args=()
  [ "$skip_dirty" -eq 1 ] && gen_skip_args+=(--skip-dirty)
  [ "$skip_gh" -eq 1 ] && gen_skip_args+=(--skip-gh)
  "$gen" --quick --sessions-only ${gen_skip_args[@]+"${gen_skip_args[@]}"} > "$tmp_quick" 2> "$tmp_err_quick" &
  pid_quick=$!
  gen_pids+=("$pid_quick")
  # Perform a full scan (including directories) in the background.
  "$gen" ${gen_skip_args[@]+"${gen_skip_args[@]}"} > "$tmp_full" 2> "$tmp_err_full" &
  pid_full=$!
  gen_pids+=("$pid_full")

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
  else
    notify_error "quick scan" "$tmp_err_quick"
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
          # A mid-stream partial may have emitted a repo's sessions but not yet
          # its worktrees; union cached worktrees so a partial (or a scan later
          # killed during restore) can only add worktrees, never drop them.
          union_cached_worktrees_into_partial "$tmp_sessions"
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
    # Record that a full scan completed so its dedicated TTL gate can throttle
    # the next one without being reset by interleaved quick-only refreshes.
    # A fast full (--skip-dirty/--skip-gh) reuses cached badges, so it must not
    # satisfy the gate that schedules real (fully enriched) full scans.
    if [ "$skip_dirty" -ne 1 ] && [ "$skip_gh" -ne 1 ]; then
      : > "$full_scan_stamp" 2> /dev/null || true
    fi
    if sanitize_rows "$tmp_full" "$tmp_sessions"; then
      publish_cache_from "$tmp_sessions" || true
    elif [ "$quick_published" -eq 0 ] && [ "$quick_ok" -eq 1 ] && [ -s "$tmp_quick" ]; then
      publish_cache_from "$tmp_quick" || true
    fi
  else
    notify_error "full scan" "$tmp_err_full"
  fi

  if [ "$full_ok" -ne 1 ] && [ "$quick_ok" -eq 1 ] && [ "$quick_published" -eq 0 ] && [ -s "$tmp_quick" ]; then
    publish_cache_from "$tmp_quick" || true
    quick_published=1
  fi

  if [ "$full_ok" -ne 1 ] && [ "$quick_ok" -ne 1 ]; then
    exit 1
  fi
fi

if [ "$quiet" -ne 1 ] && command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux display-message -d 1500 "pick_session: list updated" 2> /dev/null || true
fi

# Keep a precomputed ordered snapshot in sync so picker open can stay instant.
if [ -x "$ordered_update_cmd" ] && [ -s "$cache_file" ]; then
  "$ordered_update_cmd" --quiet > /dev/null 2>&1 &
fi
