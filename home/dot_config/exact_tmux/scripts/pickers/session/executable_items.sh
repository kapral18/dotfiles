#!/usr/bin/env bash
set -euo pipefail

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"
error_log="${cache_dir}/pick_session_index_error.log"
session_tombstone_live_grace_s="${PICK_SESSION_SESSION_TOMBSTONE_LIVE_GRACE_S:-2}"
cache_was_present=0
[ -f "$cache_file" ] && cache_was_present=1
script_dir="$(cd "$(dirname "$0")" && pwd)"

notify_error() {
  local phase="$1"
  local err="$2"
  local msg="pick_session ${phase} failed"
  if [ -n "$err" ]; then
    msg="${msg}: ${err}"
  fi
  if [ -n "${TMUX:-}" ]; then
    tmux display-message -d 5000 "$msg" 2> /dev/null || true
  fi
  printf '%s [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$$" "$msg" >> "$error_log" 2> /dev/null || true
}

ansi_wrap() {
  local code="$1"
  local text="$2"
  printf '\033[%sm%s\033[0m' "$code" "$text"
}

display_session_entry() {
  local name="$1"
  printf '%s  %s' \
    "$(ansi_wrap '38;5;42' '')" \
    "$(ansi_wrap '1;38;5;81' "$name")"
}

display_dir_entry() {
  local path_display="$1"
  printf '%s  %s' "$(ansi_wrap '38;5;75' '')" "$(ansi_wrap '38;5;110' "$path_display")"
}

wait_ms="${PICK_SESSION_CACHE_WAIT_MS:-0}"
mutation_ttl="${PICK_SESSION_MUTATION_TOMBSTONE_TTL:-300}"
if [ -n "${TMUX:-}" ]; then
  wait_ms="$(tmux show-option -gqv '@pick_session_cache_wait_ms' 2> /dev/null || printf '%s' "$wait_ms")"
  mutation_ttl="$(tmux show-option -gqv '@pick_session_mutation_tombstone_ttl' 2> /dev/null || printf '%s' "$mutation_ttl")"
  session_tombstone_live_grace_s="$(tmux show-option -gqv '@pick_session_session_tombstone_live_grace_s' 2> /dev/null || printf '%s' "$session_tombstone_live_grace_s")"
fi
case "$wait_ms" in
  '' | *[!0-9]*) wait_ms=0 ;;
esac
case "$mutation_ttl" in
  '' | *[!0-9]*) mutation_ttl=300 ;;
esac
case "$session_tombstone_live_grace_s" in
  '' | *[!0-9]*) session_tombstone_live_grace_s=2 ;;
esac

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

# Fast path for large snapshots: when there are no pending removals or
# mutation tombstones, emit the cache as-is and avoid expensive rehydration.
if [ "$cache_was_present" -eq 1 ] && [ ! -s "$mutation_file" ] && [ ! -s "$pending_file" ]; then
  fixup_current_marker "$cache_file"
  exit 0
fi

if [ "$cache_was_present" -eq 1 ]; then
  cache_has_dir_rows=0
  if awk -F $'\t' 'NF>=5 && $2 == "dir" { found=1; exit } END { exit(found?0:1) }' "$cache_file" 2> /dev/null; then
    cache_has_dir_rows=1
  fi

  # Light path: when cache has only session rows, skip full Python rehydration.
  # Tombstone filtering only (no worktree promotion).
  if awk -F $'\t' 'NF>=5 && ($2=="worktree" || $2=="dir") { exit 1 }' "$cache_file" 2> /dev/null; then
    if command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ] && command -v python3 > /dev/null 2>&1; then
      _rehydrate_err="$(mktemp -t pick_session_rehydrate_err.XXXXXX)"
      if MUTATIONS_FILE="$mutation_file" PENDING_FILE="$pending_file" MUTATION_TTL="$mutation_ttl" SESSION_TOMBSTONE_LIVE_GRACE_S="$session_tombstone_live_grace_s" python3 -u "$script_dir/lib/items_light_rehydrate.py" "$cache_file" 2> "$_rehydrate_err"; then
        rm -f "$_rehydrate_err" 2> /dev/null || true
        exit 0
      else
        notify_error "light rehydrate" "$(tail -1 "$_rehydrate_err" 2> /dev/null || true)"
        rm -f "$_rehydrate_err" 2> /dev/null || true
      fi
    fi
  fi

  # Full rehydration when cache has worktree/dir rows (session promotion, etc.)
  if command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ] && command -v python3 > /dev/null 2>&1; then
    scan_roots_raw="$(tmux show-option -gqv '@pick_session_worktree_scan_roots' 2> /dev/null || true)"
    if [ -z "${scan_roots_raw:-}" ]; then
      scan_roots_raw="$HOME/work,$HOME/code,$HOME/.backport/repositories,$HOME/.local/share"
    fi
    _rehydrate_err="$(mktemp -t pick_session_rehydrate_err.XXXXXX)"
    if MUTATIONS_FILE="$mutation_file" PENDING_FILE="$pending_file" MUTATION_TTL="$mutation_ttl" SESSION_TOMBSTONE_LIVE_GRACE_S="$session_tombstone_live_grace_s" PICK_SESSION_SCAN_ROOTS="$scan_roots_raw" python3 -u "$script_dir/lib/items_full_rehydrate.py" "$cache_file" 2> "$_rehydrate_err"; then
      rm -f "$_rehydrate_err" 2> /dev/null || true
      exit 0
    else
      notify_error "full rehydrate" "$(tail -1 "$_rehydrate_err" 2> /dev/null || true)"
      rm -f "$_rehydrate_err" 2> /dev/null || true
    fi
  fi

  # If python isn't available, still emit a 6th "match key" field so fzf can
  # prioritize name matching before paths.
  awk -F $'\t' '
	    BEGIN { OFS = "\t" }
	    NF < 5 { print; next }
	    NF >= 6 { print; next }
	    {
      kind = $2
      path = $3
      meta = $4
      target = $5
      base = path
      sub(".*/", "", base)
      mk = ""
      if (kind == "session") {
        mk = target
      } else if (kind == "worktree") {
        mk = base " " path
      } else if (kind == "dir") {
        mk = base " " path
	      } else {
	        mk = base " " path
	      }
	      print $1, kind, path, meta, target, mk
	    }
	  ' "$cache_file"
  exit 0
fi

# Kick off a background refresh if we're inside tmux.
if command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  # If the cache is missing, prefer a full refresh in the background so the
  # next open (or a ctrl-r) has complete data.
  if [ "$cache_was_present" -eq 1 ]; then
    tmux run-shell -b "$HOME/.config/tmux/scripts/pickers/session/index_update.sh --quiet --quick-only" 2> /dev/null || true
  else
    tmux run-shell -b "$HOME/.config/tmux/scripts/pickers/session/index_update.sh --quiet" 2> /dev/null || true
  fi
fi

# Fast path: when cache is empty, show sessions + recent dirs immediately.
# No wait loop — wait_ms=0 by default for instant popup.
elapsed=0
while [ "$elapsed" -lt "$wait_ms" ]; do
  if [ -f "$cache_file" ]; then
    cat "$cache_file"
    exit 0
  fi
  sleep 0.03
  elapsed="$((elapsed + 30))"
done

# Fallback: tmux sessions + zoxide recent dirs (if available) + home.
# Sort sessions by path so same-repo sessions (e.g. ~/work/kibana, ~/code/kibana) group together.
if command -v tmux > /dev/null 2>&1; then
  cur="$(tmux display-message -p '#S' 2> /dev/null || true)"
  tmp_sessions="$(mktemp -t pick_session_fallback.XXXXXX)"
  tmux list-sessions -F $'#{session_name}\t#{session_path}' 2> /dev/null | while IFS=$'\t' read -r name path; do
    [ -n "$name" ] || continue
    [ "$name" = "$cur" ] && continue
    tpath="$path"
    # shellcheck disable=SC2088
    case "$path" in
      "$HOME") tpath="~" ;;
      "$HOME"/*) tpath="~/${path#"$HOME"/}" ;;
    esac
    # shellcheck disable=SC2088
    base="$(basename "$path" 2> /dev/null || printf '%s' "$path")"
    mk="${name} ${base} ${tpath} ${path}"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(display_session_entry "$name" "$tpath")" "session" "$path" "" "$name" "$mk"
  done > "$tmp_sessions"
  [ -s "$tmp_sessions" ] && sort -t$'\t' -k3 "$tmp_sessions"
  rm -f "$tmp_sessions"
fi

# Add zoxide recent dirs (if available) for snappy discovery like tmux-session-wizard.
if command -v zoxide > /dev/null 2>&1; then
  zoxide query -l 2> /dev/null | while IFS= read -r path; do
    [ -n "$path" ] || continue
    [ -d "$path" ] || continue
    [ "$path" = "$HOME" ] && continue
    tpath="$path"
    # shellcheck disable=SC2088
    case "$path" in
      "$HOME") tpath="~" ;;
      "$HOME"/*) tpath="~/${path#"$HOME"/}" ;;
    esac
    base="$(basename "$path" 2> /dev/null || printf '%s' "$path")"
    mk="${base} ${tpath} ${path}"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(display_dir_entry "$tpath")" "dir" "$path" "" "" "$mk"
  done
fi

mk="home ~ $HOME"
printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(display_dir_entry '~')" "dir" "$HOME" "" "" "$mk"
