#!/usr/bin/env bash
set -euo pipefail

IFS='|' read -r width height < <(
  tmux display-message -p \
    '#{@gh_tfork_popup_width}|#{@gh_tfork_popup_height}' \
    2> /dev/null || true
)
[ -n "${width:-}" ] || width="90"
[ -n "${height:-}" ] || height="3"

prompt_cmd="$HOME/.config/tmux/scripts/gh_tfork/prompt.sh"

if [ ! -x "$prompt_cmd" ]; then
  tmux display-message "Missing script: $prompt_cmd"
  exit 0
fi

tmux display-popup -E -h "${height}" -w "${width}" -d "#{pane_current_path}" \
  -T "Bootstrap repo (,gh-tfork)" /bin/bash "$prompt_cmd" 2> /dev/null || true
