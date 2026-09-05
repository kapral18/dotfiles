#!/usr/bin/env bash
# tmux Alt-Enter handler.
#
# Wired from conf.d/45-agent-prompt-wrap.conf:
#   bind-key -n M-Enter run-shell "<this script> '#{pane_id}'"
#
# Per-press decision:
#   1. If @agent-wrap is not "1": pass Alt-Enter through unchanged.
#   2. If pane's foreground process is not an agent
#      (claude/cursor-agent/pi/copilot):
#      pass Alt-Enter through unchanged.
#   3. Otherwise: send Ctrl-A (cursor to start), bracketed-paste the prefix core,
#      type the "User prompt follows:" pointer (correct here because the user's
#      typed prompt is glued immediately after), then send Ctrl-E (cursor to end).
#      The prompt stays editable until the user presses Enter. The shared
#      prefix.txt holds only the discipline core; this path owns the
#      forward-pointing framing.
#
# Detection: pane_current_command alone is not sufficient (cursor-agent and pi
# both show as `node`). We inspect the foreground processes on the pane's TTY
# via `ps`, filter to running foreground process groups, and match the command line.

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

# Match the executable or Node/Bun script, never an unrelated command's arguments.
# Anchoring also excludes names such as `pip` and `pioneer`.
#   - claude / claude.exe at end of a path component
#   - cursor-agent at end of a path component
#   - pi at end of a path component
#   - copilot / copilot.exe at end of a path component
#   - pi-coding-agent npm script path (covers Node-launched pi forks)
fg_cmd="$(ps -t "$tty_short" -o pgid=,tpgid=,stat=,command= -ww 2> /dev/null \
  | awk '$1 == $2 && $3 !~ /T/ { $1 = $2 = $3 = ""; sub(/^ +/, ""); print }' || true)"
if ! printf '%s' "$fg_cmd" | grep -qE '^([^ ]*/)?(claude(\.exe)?|cursor-agent|pi|copilot(\.exe)?)( |$)|^([^ ]*/)?(node|bun)( --(use-system-ca|enable-source-maps|no-warnings))* ([^ ]*/)?((claude(\.exe)?|cursor-agent|pi|copilot(\.exe)?)( |$)|pi-coding-agent/[^ ]+( |$))'; then
  pass_through
fi

# Wrap and leave editable.
PREFIX_FILE="$HOME/.config/tmux/agent_prompts/prefix.txt"
if [ -r "$PREFIX_FILE" ] && [ -s "$PREFIX_FILE" ]; then
  tmux send-keys -t "$PANE_ID" C-a
  tmux load-buffer "$PREFIX_FILE"
  tmux paste-buffer -t "$PANE_ID" -p
  # The shared core ends at the discipline body; the user's prompt is typed
  # immediately after, so the forward-pointing pointer is accurate here.
  tmux load-buffer - <<< $'\n\n---\n\nUser prompt follows:\n\n'
  tmux paste-buffer -t "$PANE_ID" -p
  tmux send-keys -t "$PANE_ID" C-e
fi
