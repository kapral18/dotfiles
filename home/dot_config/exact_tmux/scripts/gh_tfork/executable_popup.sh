#!/usr/bin/env bash
set -euo pipefail

IFS='|' read -r width height orig_shell < <(
  tmux display-message -p \
    '#{@gh_tfork_popup_width}|#{@gh_tfork_popup_height}|#{default-shell}' \
    2> /dev/null || true
)
[ -n "${width:-}" ] || width="90"
[ -n "${height:-}" ] || height="3"
[ -n "${orig_shell:-}" ] || orig_shell="/bin/sh"

prompt_cmd="$HOME/.config/tmux/scripts/gh_tfork/prompt.sh"

if [ ! -x "$prompt_cmd" ]; then
  tmux display-message "Missing script: $prompt_cmd"
  exit 0
fi

tmux set-option -g default-shell /bin/sh \; \
  display-popup -E -h "${height}" -w "${width}" -d "#{pane_current_path}" \
  -T "Bootstrap repo (,gh-tfork)" "$prompt_cmd" \; \
  set-option -g default-shell "$orig_shell" 2> /dev/null || true
