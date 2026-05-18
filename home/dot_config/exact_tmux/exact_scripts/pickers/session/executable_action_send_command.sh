#!/usr/bin/env bash
if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
  for _b in /opt/homebrew/bin/bash /usr/local/bin/bash; do
    [ -x "$_b" ] && exec "$_b" "$0" "$@"
  done
  exit 1
fi
set -euo pipefail

sel_file="${1:-}"
cmd_file="${2:-}"

if [ -z "$sel_file" ] || [ ! -f "$sel_file" ]; then
  exit 0
fi
if [ -z "$cmd_file" ] || [ ! -f "$cmd_file" ]; then
  exit 0
fi

# `sel_file` is a per-binding mktemp snapshot minted by `dispatch_async.sh` at
# enter-time in the picker's send-mode binding. We're the last consumer and
# own its cleanup, same as the kill/remove actions.
trap 'rm -f "$sel_file" "$cmd_file" 2>/dev/null || true' EXIT

cmd="$(cat "$cmd_file" 2> /dev/null || true)"

if [ -z "$cmd" ]; then
  exit 0
fi

debug_log="${PICK_SESSION_SEND_DEBUG_LOG:-}"
log_debug() {
  [ -n "$debug_log" ] || return 0
  {
    printf '[%s] ' "$(date '+%Y-%m-%d %H:%M:%S')"
    printf '%s\n' "$*"
  } >> "$debug_log" 2> /dev/null || true
}
log_debug "send_command invoked: sel_file=$sel_file cmd=[$cmd]"

# Per-row state for worktree/dir entries we may have to spawn a session for.
# Stored as TAB-joined "kind\tpath\tmeta\ttarget" so we keep the cache fields
# needed by session_name_for_entry (in lib/session_naming.sh), which mirrors
# pick_session.sh's repo/branch naming convention. Without meta/target we'd
# diverge from the canonical session name and the picker would show a
# duplicate-looking row until the user did a regular `enter` (which renames any
# path-matching session to the canonical name).
declare -a sess=()
declare -a entries=()

while IFS= read -r _line; do
  [ -n "$_line" ] || continue
  mapfile -t _fields < <(awk -F $'\t' '{print $1; print $2; print $3; print $4; print $5}' <<< "$_line")
  kind="${_fields[1]-}"
  path="${_fields[2]-}"
  meta="${_fields[3]-}"
  target="${_fields[4]-}"

  if [ "$kind" = "session" ] && [ -n "$target" ]; then
    sess+=("$target")
  elif [ "$kind" = "dir" ] || [ "$kind" = "worktree" ]; then
    [ -n "$path" ] || continue
    entries+=("${kind}"$'\t'"${path}"$'\t'"${meta}"$'\t'"${target}")
  fi
done < "$sel_file"

log_debug "parsed: sess=[${sess[*]+${sess[*]}}] entries=${#entries[@]}"

# Shared naming/path helpers live in lib/session_naming.sh so this script and
# pick_session.sh produce identical canonical names (a divergent name would
# manifest as a stray-looking row in the picker until the user's next `enter`
# triggered the picker's path-keyed rename). See that file for the contract.
# shellcheck source=lib/session_naming.sh
# shellcheck disable=SC1091
. "$HOME/.config/tmux/scripts/pickers/session/lib/session_naming.sh"

# Read the configured mode so `dir` rows get the same name pick_session.sh
# would on regular `enter`. Defaults to `directory`, matching pick_session.sh.
_pick_session_mode="$(tmux show-option -gqv @pick_session_mode 2> /dev/null || true)"
: "${_pick_session_mode:=directory}"

declare -a spawned=()
declare -a spawn_failed=()

if [ ${#entries[@]} -gt 0 ] && command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  # Build (rpath, name) lookup over live sessions so we can match selected
  # worktree/dir rows against existing sessions before spawning new ones.
  declare -A live_paths=()
  while IFS=$'\t' read -r _ln _lp; do
    [ -n "$_ln" ] || continue
    [ -n "$_lp" ] || continue
    _lp="$(realpath "$_lp" 2> /dev/null || printf '%s' "$_lp")"
    # Last wins on collisions; good enough for matching.
    live_paths["$_lp"]="$_ln"
  done < <(tmux list-sessions -F $'#{session_name}\t#{session_path}' 2> /dev/null || true)

  for _entry in "${entries[@]}"; do
    IFS=$'\t' read -r kind path meta target <<< "$_entry"
    rd="$(realpath "$path" 2> /dev/null || printf '%s' "$path")"
    matched=""
    if [ -n "${live_paths["$rd"]-}" ]; then
      matched="${live_paths["$rd"]}"
    elif [ "$kind" = "worktree" ]; then
      # "Session under selected path" fallback applies only to worktree rows,
      # where it's expected that a session opened in a deeper subdirectory of
      # the worktree still represents that worktree. For `dir` rows, this rule
      # over-matches dramatically (selecting $HOME would match every session
      # under the home directory and route the command to whichever one was
      # iterated first); restrict it to worktrees so dir rows always spawn or
      # exact-match.
      for _lp in "${!live_paths[@]}"; do
        if [[ "$_lp" == "$rd"/* ]]; then
          matched="${live_paths["$_lp"]}"
          break
        fi
      done
    fi
    if [ -n "$matched" ]; then
      sess+=("$matched")
      continue
    fi

    # Unmatched: spawn a session for this entry so the command can be sent.
    # The cache's target field is the worktree root for worktree rows (not
    # necessarily the selected path), so pass it through to keep branch fallback
    # and canonical naming identical to pick_session.sh's enter path.
    name="$(session_name_for_entry "$kind" "$path" "$meta" "$target" "$_pick_session_mode" 2> /dev/null || true)"
    if [ -z "$name" ]; then
      spawn_failed+=("$path")
      continue
    fi
    if tmux has-session -t "=${name}" 2> /dev/null; then
      # Name collision: first try the lib's bag-recovery flow (same as
      # pick_session.sh's enter path) — if the holder is a bagged session,
      # rename it away and reuse the canonical name. Only when bag-recovery
      # is not applicable do we fall back to a path-basename suffix so the
      # command still reaches a fresh session; on the next regular `enter`,
      # pick_session.sh's path-keyed rename will move whichever session is
      # at the actual path back to the canonical name.
      # Discard the lib's "OLD\tNEW" stdout — we don't maintain a session
      # cache here, so the advisory rename pair is noise. Keep the return code
      # (0 = name now usable, 1 = collision unresolved).
      if ! bag_rename_if_needed "$name" "$path" > /dev/null; then
        _suffix="$(basename "$path" 2> /dev/null || true)"
        [ -n "$_suffix" ] || _suffix="adhoc"
        name="${name}@${_suffix}"
        name="$(tmux_sanitize_session_name "$name" 2> /dev/null || printf '%s' "$name")"
        log_debug "name collision (non-bag); fallback to suffix: $name"
      else
        log_debug "name collision resolved via bag-rename: $name"
      fi
    fi
    if tmux new-session -d -s "$name" -c "$path" "$(login_shell)" 2> /dev/null; then
      spawned+=("$name")
      sess+=("$name")
      log_debug "spawned session: name=$name path=$path kind=$kind"
    else
      spawn_failed+=("$path")
      log_debug "spawn failed: path=$path kind=$kind name=$name"
    fi
  done
fi

# If we just spawned shells, give them a brief moment to initialize before
# send-keys, otherwise the first keystrokes can race the shell's readline init
# and get dropped (especially fish/zsh with prompt instrumentation).
if [ ${#spawned[@]} -gt 0 ]; then
  sleep 0.3
fi

if [ ${#sess[@]} -gt 0 ]; then
  mapfile -t sess < <(printf '%s\n' "${sess[@]}" | sort -u)
fi

log_debug "final sess=[${sess[*]+${sess[*]}}] spawned=[${spawned[*]+${spawned[*]}}] spawn_failed=[${spawn_failed[*]+${spawn_failed[*]}}]"

if [ ${#sess[@]} -eq 0 ]; then
  if [ ${#spawn_failed[@]} -gt 0 ] && command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
    tmux display-message -d 3000 "pick_session: ctrl-s could not spawn sessions for ${#spawn_failed[@]} selected path(s)" 2> /dev/null || true
  fi
  exit 0
fi

declare -i sent_ok=0
declare -i sent_fail=0
declare -a failed_sessions=()
for s in "${sess[@]}"; do
  # Each iteration is wrapped in its own subshell so a transient tmux failure
  # (e.g. a session that disappeared between selection and dispatch) cannot
  # abort the loop and skip the remaining sessions. The `|| rc=$?` form
  # suppresses outer `set -e` so we can record the per-session result.
  rc=0
  (
    set +e
    panes="$(tmux list-panes -s -t "$s" -F '#{window_index}.#{pane_index} #{pane_current_command}' 2> /dev/null)"
    panes_rc=$?
    if [ "$panes_rc" -ne 0 ] || [ -z "$panes" ]; then
      exit 2
    fi

    target_pane=""
    while read -r pane_id p_cmd; do
      [ -n "$pane_id" ] || continue
      case "$p_cmd" in
        fish | zsh | bash | sh)
          target_pane="$pane_id"
          break
          ;;
      esac
    done <<< "$panes"

    if [ -z "$target_pane" ]; then
      target_pane="$(printf '%s\n' "$panes" | awk 'NF{print $1; exit}')"
    fi

    if [ -z "$target_pane" ]; then
      exit 3
    fi

    tmux send-keys -t "=${s}:${target_pane}" "$cmd" C-m
  ) || rc=$?
  if [ "$rc" -eq 0 ]; then
    sent_ok=$((sent_ok + 1))
    log_debug "sent OK: session=$s"
  else
    sent_fail=$((sent_fail + 1))
    failed_sessions+=("$s")
    log_debug "send failed: session=$s (rc=$rc)"
  fi
done

if [ "$sent_fail" -gt 0 ] && command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux display-message -d 3000 "pick_session: sent to ${sent_ok}/${#sess[@]} session(s); failed: ${failed_sessions[*]}" 2> /dev/null || true
elif [ ${#spawn_failed[@]} -gt 0 ] && command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux display-message -d 3000 "pick_session: sent to ${sent_ok}/${#sess[@]} session(s); failed to spawn ${#spawn_failed[@]} path(s)" 2> /dev/null || true
fi

# Now that any spawn-and-send work is done, poke the still-open picker so
# newly-created sessions become visible without the user having to hit
# ctrl-r. We post `reload($filter_cmd --refresh --force-order)+track` via
# fzf's --listen socket (FZF_SOCK / FZF_PORT are propagated by
# dispatch_async.sh; the picker's transform shell always has them when
# --listen is active).
#
# `--refresh` runs a synchronous quick scan that picks up the sessions we
# just spawned; `--force-order` keeps the grouped output consistent with
# what the picker rendered on open. The +track inside fzf_reload.sh pins
# the highlighted row across the reload so the visible order around the
# user's cursor stays as stable as the new cache contents allow.
#
# Only triggered when this run actually created new sessions: sending to
# existing sessions doesn't change the cache, so the post would be churn
# (re-rendering the same items in the same order). Skipped when the picker
# socket is unreachable (e.g. user closed the picker before we finished
# spawning) -- curl fails silently and the next ctrl-r / live_refresh tick
# will still catch up.
if [ ${#spawned[@]} -gt 0 ]; then
  fzf_reload_cmd="$HOME/.config/tmux/scripts/pickers/session/fzf_reload.sh"
  filter_cmd="$HOME/.config/tmux/scripts/pickers/session/filter.sh"
  if [ -x "$fzf_reload_cmd" ] && [ -x "$filter_cmd" ] \
    && { [ -n "${FZF_SOCK:-}" ] || [ -n "${FZF_PORT:-}" ]; }; then
    "$fzf_reload_cmd" "$filter_cmd --refresh --force-order" 0 > /dev/null 2>&1 || true
    log_debug "posted picker reload via fzf_reload.sh"
  fi
fi

exit 0
