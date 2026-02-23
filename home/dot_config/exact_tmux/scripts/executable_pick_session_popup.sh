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

height="$(tmux_opt '@pick_session_popup_height' '40')"
width="$(tmux_opt '@pick_session_popup_width' '80')"

set +e
tmux display-popup -E -h "${height}%" -w "${width}%" -d "#{pane_current_path}" "$HOME/.config/tmux/scripts/pick_session.sh"
rc="$?"
set -e

# User-cancel should not show as "returned 130".
if [ "$rc" -eq 130 ]; then
  exit 0
fi
exit "$rc"
