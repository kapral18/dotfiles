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

login_shell() {
  local s=""
  s="$(python3 -c 'import os,pwd; print(pwd.getpwuid(os.getuid()).pw_shell)' 2> /dev/null || true)"
  if [ -n "$s" ] && [ -x "$s" ]; then
    printf '%s\n' "$s"
    return 0
  fi
  if command -v fish > /dev/null 2>&1; then
    command -v fish
    return 0
  fi
  printf '%s\n' "/bin/sh"
}

# Use the configured login shell rather than $SHELL (tmux may set SHELL=/bin/sh
# inside popups for snappy rendering).
shell="$(login_shell)"

if [ "$pending_spawn" = "1" ]; then
  pane_id="$(tmux list-panes -t "$session" -F '#{pane_id}' 2> /dev/null | head -n 1)"
  if [ -n "$pane_id" ]; then
    tmux respawn-pane -k -t "$pane_id" -c "$dir" "$shell" 2> /dev/null || true
  fi
  set_opt "@pick_session_lazy_spawn_pending" "0"
fi

if [ "$pending_split" = "1" ]; then
  win="$(tmux list-windows -t "$session" -F '#{window_id}' 2> /dev/null | head -n 1)"
  if [ -n "$win" ]; then
    panes="$(tmux display-message -p -t "$win" '#{window_panes}' 2> /dev/null || printf '0')"
    case "$panes" in
      '' | *[!0-9]*) panes=0 ;;
    esac
    if [ "$panes" -lt 2 ]; then
      tmux split-window -h -t "$win" -c "$dir" "$shell" 2> /dev/null || true
      tmux select-layout -t "$win" even-horizontal > /dev/null 2>&1 || true
    fi
  fi
  set_opt "@pick_session_lazy_split_pending" "0"
fi
