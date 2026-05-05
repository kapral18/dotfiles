#!/usr/bin/env bash
set -euo pipefail

start_dir="${1:-$HOME}"

sock="gh-dash-popup"
session_work="work"
session_home="home"
tmux_conf="$HOME/.config/tmux/gh-dash-popup.conf"
config_work="$HOME/.config/gh-dash/config-work.yml"
config_home="$HOME/.config/gh-dash/config-home.yml"

show_popup() {
  local attach_args=()
  if [ -n "${1:-}" ]; then
    attach_args=(-t "$1")
  fi
  local orig_shell
  orig_shell="$(tmux show-option -gqv default-shell 2> /dev/null || echo /bin/sh)"
  tmux set-option -g default-shell /bin/sh \; \
    display-popup -E -h 90% -w 90% -d "${start_dir}" -T "gh-dash" \
    "tmux -L '${sock}' attach ${attach_args[*]:-}" \; \
    set-option -g default-shell "$orig_shell" 2> /dev/null || true
}

# Fast path: if either session is alive, skip dependency checks.
# tmux attach (no -t) reconnects to the most recently used session.
if tmux -L "${sock}" has-session -t "${session_work}" 2> /dev/null \
  || tmux -L "${sock}" has-session -t "${session_home}" 2> /dev/null; then
  tmux -L "${sock}" source-file "${tmux_conf}" > /dev/null 2>&1 || true
  show_popup
  exit 0
fi

# Cold path: first open — verify dependencies, create both sessions.
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
dash_cmd() { printf 'while true; do gh dash --config "%s"; sleep 1; done' "$1"; }

tmux -L "${sock}" -f "${tmux_conf}" new-session -d -s "${session_work}" -c "${start_dir}" \
  "bash -lc '${env_vars}; $(dash_cmd "${config_work}")'"

tmux -L "${sock}" new-session -d -s "${session_home}" -c "${start_dir}" \
  "bash -lc '${env_vars}; $(dash_cmd "${config_home}")'"

show_popup "${session_work}"
