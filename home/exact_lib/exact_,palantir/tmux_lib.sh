# Unified tmux primitives for ,palantir shell commands. Python modules use
# composer.py's equivalent outer-socket-aware transport. Consolidates the shell
# wrapper from home/exact_lib/exact_shared/worktree_lib.sh (_comma_w_tmux) with the pane
# resolution the tmux pickers use. Subcommand scripts source this file; it
# defines functions only and never runs anything on import.

# tmux wrapper that targets the outer tmux server when invoked from inside a
# nested popup. The popup launcher exports OUTER_TMUX_SOCKET; otherwise we talk
# to the default server.
_palantir_tmux() {
  if ! command -v tmux > /dev/null 2>&1; then
    return 127
  fi
  if [ -n "${OUTER_TMUX_SOCKET:-}" ]; then
    tmux -S "${OUTER_TMUX_SOCKET}" "$@"
    return $?
  fi
  tmux "$@"
}

# Resolve the user's login shell, preferring the passwd entry, then fish, then sh.
_palantir_login_shell() {
  local s=""
  s="$(python3 -c 'import os,pwd; print(pwd.getpwuid(os.getuid()).pw_shell)' 2> /dev/null || true)"
  if [ -n "$s" ] && [ -x "$s" ]; then
    printf '%s\n' "$s"
    return 0
  fi
  command -v fish 2> /dev/null || printf '%s\n' /bin/sh
}

# Derive a stable, tmux-legal session name for one legion. tmux forbids '.' and
# ':' in session names, so sanitize up-front the same way ,w does.
_palantir_session_name() {
  local legion_id="$1"
  printf '%s\n' "legion-${legion_id}" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9_-]+/_/g; s/[.:]+/_/g; s/_+$//'
}

_palantir_has_session() {
  local name="$1"
  _palantir_tmux has-session -t "$name" 2> /dev/null
}

_palantir_kill_session() {
  local name="$1"
  _palantir_tmux kill-session -t "$name" 2> /dev/null || true
}

# Spawn a detached legion session rooted at a worktree, window 0 named
# "command". Returns 0 on spawn (including when the session already existed),
# 1 if tmux is unavailable.
_palantir_spawn_session() {
  local name="$1"
  local cwd="$2"
  if ! command -v tmux > /dev/null 2>&1; then
    return 1
  fi
  if _palantir_has_session "$name"; then
    return 0
  fi
  local shell
  shell="$(_palantir_login_shell)"
  _palantir_tmux new-session -d -s "$name" -n command -c "$cwd" "$shell" 2> /dev/null
}

# Print the names of live legion sessions (one per line). Filters to the
# legion- prefix so non-palantir sessions are never touched by sweeps.
_palantir_list_sessions() {
  _palantir_tmux list-sessions -F '#{session_name}' 2> /dev/null | grep '^legion-' || true
}

# Quote one shell word for commands sent to a pane.
_palantir_sh_quote() {
  local s="$1"
  printf "'"
  printf '%s' "$s" | sed "s/'/'\\\\''/g"
  printf "'"
}
