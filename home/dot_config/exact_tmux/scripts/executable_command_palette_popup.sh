#!/usr/bin/env bash
set -euo pipefail

IFS='|' read -r height width < <(
  tmux display-message -p \
    '#{@command_palette_popup_height}|#{@command_palette_popup_width}' \
    2>/dev/null || true
)
[ -n "${height:-}" ] || height="60"
[ -n "${width:-}" ] || width="70"

tmux display-popup -E -h "${height}%" -w "${width}%" \
  "$HOME/.config/tmux/scripts/command_palette.sh" 2>/dev/null || true
