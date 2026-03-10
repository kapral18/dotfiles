#!/usr/bin/env bash
set -euo pipefail

orig_shell="$(tmux show-option -gqv default-shell 2>/dev/null || echo /bin/sh)"

tmux set-option -g default-shell /bin/sh \; \
  display-popup -E ",tmux-run-all '*' '' 'exec fish'" \; \
  set-option -g default-shell "$orig_shell" 2>/dev/null || true
