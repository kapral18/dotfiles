#!/usr/bin/env bash
set -euo pipefail

session="${1:-}"

if ! command -v tmux > /dev/null 2>&1; then
  exit 0
fi

if [ -z "$session" ]; then
  session="$(tmux display-message -p '#S' 2> /dev/null || true)"
fi
[ -n "$session" ] || exit 0

# Record this switch as a frecency access so the picker can order rows by usage
# (zoxide-style). Runs on every client-session-changed event regardless of the
# lazy-spawn/split fast-path below, since a switch is the real "I used this"
# signal. Best-effort and backgrounded so it never delays the switch.
if command -v python3 > /dev/null 2>&1; then
  _switch_path="$(tmux display-message -p -t "$session" '#{session_path}' 2> /dev/null || true)"
  if [ -n "$_switch_path" ]; then
    _frecency_lib_dir="$HOME/.config/tmux/scripts/pickers/session/lib"
    PYTHONPATH="$_frecency_lib_dir:${PYTHONPATH:-}" python3 -c 'import sys, frecency; frecency.add(sys.argv[1])' "$_switch_path" > /dev/null 2>&1 &
  fi
fi

opt() {
  tmux show-option -t "$session" -qv "$1" 2> /dev/null || true
}

set_opt() {
  tmux set-option -t "$session" -q "$1" "$2" > /dev/null 2>&1 || true
}

pending_spawn="$(opt "@pick_session_lazy_spawn_pending")"
pending_split="$(opt "@pick_session_lazy_split_pending")"

[ "$pending_spawn" = "1" ] || [ "$pending_split" = "1" ] || exit 0

dir="$(tmux display-message -p -t "$session" '#{session_path}' 2> /dev/null || true)"
if [ -z "$dir" ] || [ ! -d "$dir" ]; then
  dir="$HOME"
fi

# Use $SHELL when it looks like a real login shell; fall back to passwd lookup
# only if $SHELL is /bin/sh (tmux popups override SHELL for snappy rendering,
# but this hook runs in a regular run-shell context where SHELL is correct).
shell="${SHELL:-/bin/sh}"
case "$shell" in
  */sh)
    shell="$(dscl . -read /Users/"$USER" UserShell 2> /dev/null | awk '{print $2}')"
    if [ -z "$shell" ] || [ ! -x "$shell" ]; then
      shell="$(getent passwd "$USER" 2> /dev/null | cut -d: -f7)"
    fi
    if [ -z "$shell" ] || [ ! -x "$shell" ]; then
      shell="$(command -v fish 2> /dev/null || echo /bin/sh)"
    fi
    ;;
esac

if [ "$pending_spawn" = "1" ]; then
  pane_id="$(tmux list-panes -t "$session" -F '#{pane_id}' 2> /dev/null | head -n 1)"
  if [ -n "$pane_id" ]; then
    tmux respawn-pane -k -t "$pane_id" -c "$dir" "$shell" 2> /dev/null || true
  fi
  set_opt "@pick_session_lazy_spawn_pending" "0"
fi

if [ "$pending_split" = "1" ]; then
  # Defer the split so the first pane renders immediately. Without this,
  # both panes launch shell+prompt (e.g. fish+starship) synchronously,
  # which can take several seconds on large repos like kibana.
  _qs="$(printf %q "$session")"
  _qd="$(printf %q "$dir")"
  _qsh="$(printf %q "$shell")"
  tmux run-shell -b "sleep 0.3; \
    win=\$(tmux list-windows -t ${_qs} -F '##{window_id}' 2>/dev/null | head -n 1); \
    [ -n \"\$win\" ] || exit 0; \
    panes=\$(tmux display-message -p -t \"\$win\" '##{window_panes}' 2>/dev/null || printf 0); \
    case \"\$panes\" in ''|*[!0-9]*) panes=0;; esac; \
    [ \"\$panes\" -lt 2 ] || exit 0; \
    tmux split-window -h -t \"\$win\" -c ${_qd} ${_qsh} 2>/dev/null; \
    tmux select-layout -t \"\$win\" even-horizontal 2>/dev/null; \
    tmux set-option -t ${_qs} -q @pick_session_lazy_split_pending 0 2>/dev/null" \
    2> /dev/null || true
fi
