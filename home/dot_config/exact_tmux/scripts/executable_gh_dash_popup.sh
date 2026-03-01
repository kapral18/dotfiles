#!/usr/bin/env bash
set -euo pipefail

start_dir="${1:-$HOME}"

sock="gh-dash-popup"
session="gh-dash"
tmux_conf="$HOME/.config/tmux/gh-dash-popup.conf"

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

# The `dash` subcommand is provided by the gh-dash extension.
if ! gh dash --version >/dev/null 2>&1; then
  tmux display-message "gh dash not available (is gh-dash installed?)"
  exit 127
fi

# Ensure the nested server exists with our config loaded.
if ! tmux -L "${sock}" has-session -t "${session}" 2>/dev/null; then
  tmux -L "${sock}" -f "${tmux_conf}" new-session -d -s "${session}" -c "${start_dir}" \
    "bash -lc 'export GH_DASH_POPUP=1; export OUTER_TMUX_SOCKET=\"${outer_socket}\"; export OUTER_TMUX_CLIENT=\"${outer_client}\"; exec gh dash'"
fi

# Make sure detach bindings are present (no-op if already sourced).
tmux -L "${sock}" source-file "${tmux_conf}" >/dev/null 2>&1 || true

set +e
tmux display-popup -E -h 90% -w 90% -d "${start_dir}" -T "gh-dash" "tmux -L '${sock}' attach -t '${session}'"
rc="$?"
set -e

# User-cancel / detach should not bubble as an error.
if [ "$rc" -eq 130 ]; then
  exit 0
fi
exit "$rc"
