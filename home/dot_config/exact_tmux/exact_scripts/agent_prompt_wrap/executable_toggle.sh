#!/usr/bin/env bash
# Toggle the @agent-wrap option on/off, with status-line feedback.
#
# Wired from conf.d/45-agent-prompt-wrap.conf:
#   bind-key W run-shell -b "<this script>"

set -uo pipefail

current="$(tmux show -gv @agent-wrap 2> /dev/null)"
current="${current:-1}"

if [ "$current" = "1" ]; then
  tmux set -g @agent-wrap "0"
  tmux display-message "Agent prompt wrap: OFF"
else
  tmux set -g @agent-wrap "1"
  tmux display-message "Agent prompt wrap: ON"
fi
