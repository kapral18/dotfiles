#!/usr/bin/env bash
set -euo pipefail

tmux_opt() {
  local key="$1"
  local default_value="$2"
  local value
  value="$(tmux show-option -gqv "${key}")"
  if [[ -n "${value}" ]]; then
    echo "${value}"
  else
    echo "${default_value}"
  fi
}

width="$(tmux_opt '@gh_tfork_popup_width' '90')"
height="$(tmux_opt '@gh_tfork_popup_height' '3')"

prompt_cmd="$HOME/.config/tmux/scripts/gh_tfork_prompt.sh"

if [ ! -x "$prompt_cmd" ]; then
  tmux display-message "Missing script: $prompt_cmd"
  exit 0
fi

set +e
tmux display-popup -E -h "${height}" -w "${width}" -d "#{pane_current_path}" -T "Bootstrap repo (,gh-tfork)" \
  "$prompt_cmd"
rc="$?"
set -e

if [ "$rc" -eq 130 ]; then
  exit 0
fi
exit "$rc"
