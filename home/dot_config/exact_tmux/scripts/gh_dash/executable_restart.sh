#!/usr/bin/env bash
set -euo pipefail

sock="gh-dash-popup"

# Restart the nested tmux server that hosts gh-dash.
tmux -L "${sock}" kill-server >/dev/null 2>&1 || true

tmux display-message "gh-dash popup restarted"
