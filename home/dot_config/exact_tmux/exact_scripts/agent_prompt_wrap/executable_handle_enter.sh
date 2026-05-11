#!/usr/bin/env bash
# tmux Alt-Enter handler.
#
# Wired from conf.d/45-agent-prompt-wrap.conf:
#   bind-key -n M-Enter run-shell "<this script> '#{pane_id}'"
#
# Per-press decision:
#   1. If @agent-wrap is not "1": pass Alt-Enter through unchanged.
#   2. If pane's foreground process is not an agent (claude/cursor-agent/pi):
#      pass Alt-Enter through unchanged.
#   3. Otherwise: send Ctrl-A (cursor to start), bracketed-paste the prefix,
#      send Ctrl-E (cursor to end), send Enter (submit).
#
# Detection: pane_current_command alone is not sufficient (cursor-agent and pi
# both show as `node`). We inspect the foreground processes on the pane's TTY
# via `ps -t <tty> -o command=` and pattern-match the full command line.

set -uo pipefail

PANE_ID="${1:-}"
[ -z "$PANE_ID" ] && exit 0

pass_through() {
  tmux send-keys -t "$PANE_ID" M-Enter
  exit 0
}

# Toggle (defaults to ON if option is unset)
toggle="$(tmux show -gv @agent-wrap 2> /dev/null)"
[ "${toggle:-1}" != "1" ] && pass_through

# Foreground command line for the pane's TTY
pane_tty="$(tmux display -p -t "$PANE_ID" '#{pane_tty}' 2> /dev/null || true)"
tty_short="${pane_tty#/dev/}"
[ -z "$tty_short" ] && pass_through

# Match full command lines. Anchored to avoid matching e.g. `pip` for `pi`,
# `pioneer` for `pi`, or any binary that merely contains the substring.
#   - claude / claude.exe at end of a path component
#   - cursor-agent at end of a path component
#   - pi at end of a path component
#   - pi-coding-agent npm module path (covers Node-launched pi forks)
fg_cmd="$(ps -t "$tty_short" -o command= -ww 2> /dev/null || true)"
if ! printf '%s' "$fg_cmd" | grep -qE '(/|^)(claude(\.exe)?|cursor-agent|pi)( |$)|pi-coding-agent'; then
  pass_through
fi

# Wrap and submit
PREFIX_FILE="$HOME/.config/tmux/agent_prompts/prefix.txt"
if [ -r "$PREFIX_FILE" ] && [ -s "$PREFIX_FILE" ]; then
  tmux send-keys -t "$PANE_ID" C-a
  tmux load-buffer "$PREFIX_FILE"
  tmux paste-buffer -t "$PANE_ID" -p
  tmux send-keys -t "$PANE_ID" C-e
fi

tmux send-keys -t "$PANE_ID" Enter
