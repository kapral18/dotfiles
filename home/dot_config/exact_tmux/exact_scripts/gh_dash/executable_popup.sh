#!/usr/bin/env bash
set -euo pipefail

start_dir="${1:-$HOME}"

sock="gh-dash-popup"
session="dash"
tmux_conf="$HOME/.config/tmux/gh-dash-popup.conf"
config="$HOME/.config/gh-dash/config.yml"

show_loader() {
  tmux display-message -d 5000 "gh-dash: Loading... $1" 2> /dev/null || true
}

show_popup() {
  local orig_shell
  orig_shell="$(tmux show-option -gqv default-shell 2> /dev/null || echo /bin/sh)"
  tmux set-option -g default-shell /bin/sh \; \
    display-popup -E -h 90% -w 90% -d "${start_dir}" -T "gh-dash" \
    "tmux -L '${sock}' attach -t '${session}'" \; \
    set-option -g default-shell "$orig_shell" 2> /dev/null || true
}

# Fast path: if the session is alive, skip dependency checks.
if tmux -L "${sock}" has-session -t "${session}" 2> /dev/null; then
  tmux -L "${sock}" source-file "${tmux_conf}" > /dev/null 2>&1 || true
  show_popup
  exit 0
fi

# Cold path: first open — verify dependencies, create the session.
show_loader "starting dashboard"
outer_socket=""
outer_client=""
if [ -n "${TMUX:-}" ]; then
  outer_socket="${TMUX%%,*}"
  outer_client="$(tmux display-message -p '#{client_name}' 2> /dev/null || true)"
fi

if ! command -v gh > /dev/null 2>&1; then
  tmux display-message "gh not found"
  exit 127
fi

if ! gh dash --version > /dev/null 2>&1; then
  tmux display-message "gh dash not available (is gh-dash installed?)"
  exit 127
fi

env_vars="export GH_DASH_POPUP=1; export OUTER_TMUX_SOCKET=\"${outer_socket}\"; export OUTER_TMUX_CLIENT=\"${outer_client}\""

# Auto-respawn: if gh-dash crashes the session stays alive and restarts it.
# The loop exits cleanly when the tmux server is killed (C-g restart).
dash_cmd="while true; do gh dash --config \"${config}\"; sleep 1; done"

tmux -L "${sock}" -f "${tmux_conf}" new-session -d -s "${session}" -c "${start_dir}" \
  "bash -lc '${env_vars}; ${dash_cmd}'"

show_popup
