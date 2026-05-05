#!/usr/bin/env bash
set -euo pipefail

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
session_dir="$HOME/.config/tmux/scripts/pickers/session"
github_dir="$HOME/.config/tmux/scripts/pickers/github"

IFS='|' read -r ps_h ps_w orig_shell < <(
  tmux display-message -p \
    '#{@pick_session_popup_height}|#{@pick_session_popup_width}|#{default-shell}' \
    2> /dev/null || true
)
[ -n "${ps_h:-}" ] || ps_h="40"
[ -n "${ps_w:-}" ] || ps_w="80"
[ -n "${orig_shell:-}" ] || orig_shell="/bin/sh"

gh_h="95"
gh_w="95"

rm -f "${cache_dir}/pick_session_switch_gh" "${cache_dir}/gh_picker_switch_sessions" 2> /dev/null || true

run_popup() {
  local h="$1" w="$2" cmd="$3"
  tmux set-option -g default-shell /bin/sh \; \
    display-popup -E -h "${h}%" -w "${w}%" -d "#{pane_current_path}" "$cmd" \; \
    set-option -g default-shell "$orig_shell" 2> /dev/null || true
}

run_popup "$ps_h" "$ps_w" "$session_dir/pick_session.sh"

while [ -f "${cache_dir}/pick_session_switch_gh" ]; do
  rm -f "${cache_dir}/pick_session_switch_gh" 2> /dev/null || true
  run_popup "$gh_h" "$gh_w" "$github_dir/gh_picker.sh"

  if [ -f "${cache_dir}/gh_picker_switch_sessions" ]; then
    rm -f "${cache_dir}/gh_picker_switch_sessions" 2> /dev/null || true
    run_popup "$ps_h" "$ps_w" "$session_dir/pick_session.sh"
  fi
done
