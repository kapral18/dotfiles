#!/usr/bin/env bash
set -euo pipefail

start_dir="${1:-$HOME}"

sock="gh-dash-popup"
session="gh-dash"
tmux_conf="$HOME/.config/tmux/gh-dash-popup.conf"

# Fast path: if the nested session is already alive, skip all dependency checks
# and jump straight to the popup.  This saves ~80ms (gh dash --version alone is
# ~67ms) on every subsequent open.
if tmux -L "${sock}" has-session -t "${session}" 2>/dev/null; then
  tmux -L "${sock}" source-file "${tmux_conf}" >/dev/null 2>&1 || true
  orig_shell="$(tmux show-option -gqv default-shell 2>/dev/null || echo /bin/sh)"
  tmux set-option -g default-shell /bin/sh \; \
    display-popup -E -h 90% -w 90% -d "${start_dir}" -T "gh-dash" \
    "tmux -L '${sock}' attach -t '${session}'" \; \
    set-option -g default-shell "$orig_shell" 2>/dev/null || true
  exit 0
fi

# Cold path: first open — verify dependencies, create the nested session.
outer_socket=""
outer_client=""
if [ -n "${TMUX:-}" ]; then
  outer_socket="${TMUX%%,*}"
  outer_client="$(tmux display-message -p '#{client_name}' 2>/dev/null || true)"
fi

if ! command -v gh >/dev/null 2>&1; then
  tmux display-message "gh not found"
  exit 127
fi

if ! gh dash --version >/dev/null 2>&1; then
  tmux display-message "gh dash not available (is gh-dash installed?)"
  exit 127
fi

tmux -L "${sock}" -f "${tmux_conf}" new-session -d -s "${session}" -c "${start_dir}" \
  "bash -lc 'export GH_DASH_POPUP=1; export OUTER_TMUX_SOCKET=\"${outer_socket}\"; export OUTER_TMUX_CLIENT=\"${outer_client}\"; exec gh dash'"

orig_shell="$(tmux show-option -gqv default-shell 2>/dev/null || echo /bin/sh)"
tmux set-option -g default-shell /bin/sh \; \
  display-popup -E -h 90% -w 90% -d "${start_dir}" -T "gh-dash" \
  "tmux -L '${sock}' attach -t '${session}'" \; \
  set-option -g default-shell "$orig_shell" 2>/dev/null || true
