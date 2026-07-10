#!/usr/bin/env bash
set -euo pipefail

session_dir="$HOME/.config/tmux/scripts/pickers/session"
github_dir="$HOME/.config/tmux/scripts/pickers/github"
handoff_namespace_cmd="$HOME/.config/tmux/scripts/pickers/lib/handoff_namespace.py"

die() {
  tmux display-message "$1" 2> /dev/null || true
  exit 0
}

resolve_handoff_slot() {
  local slot="$1"
  local path=""
  path="$("$handoff_namespace_cmd" path "$slot" --token "$handoff_token" 2> /dev/null || true)"
  [ -n "$path" ] || die "tmux: failed to resolve handoff slot: $slot"
  printf '%s\n' "$path"
}

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

[ -x "$handoff_namespace_cmd" ] || die "tmux: missing script: $handoff_namespace_cmd"

handoff_token="$("$handoff_namespace_cmd" begin --owner-pid "$$" --owner-role popup-loop --entry session-popup 2> /dev/null || true)"
[ -n "$handoff_token" ] || die "tmux: failed to initialize handoff namespace"
export TMUX_PICKER_HANDOFF_TOKEN="$handoff_token"

switch_to_gh_file="$(resolve_handoff_slot pick_session_switch_gh)"
switch_to_sessions_file="$(resolve_handoff_slot gh_picker_switch_sessions)"
_popup_cleanup_done=0
cleanup_popup_namespace() {
  [ "${_popup_cleanup_done:-0}" -eq 0 ] || return 0
  _popup_cleanup_done=1
  "$handoff_namespace_cmd" end --owner-pid "$$" --token "$handoff_token" > /dev/null 2>&1 || true
}
trap 'exit 0' INT HUP TERM
trap cleanup_popup_namespace EXIT

run_popup() {
  local h="$1" w="$2" cmd="$3"
  tmux set-option -g default-shell /bin/sh \; \
    display-popup -E -e "TMUX_PICKER_HANDOFF_TOKEN=${handoff_token}" -h "${h}%" -w "${w}%" -d "#{pane_current_path}" "$cmd" \; \
    set-option -g default-shell "$orig_shell" 2> /dev/null || true
}

run_popup "$ps_h" "$ps_w" "$session_dir/pick_session.sh"

while [ -f "$switch_to_gh_file" ]; do
  rm -f "$switch_to_gh_file" 2> /dev/null || true
  run_popup "$gh_h" "$gh_w" "$github_dir/gh_picker.sh"

  if [ -f "$switch_to_sessions_file" ]; then
    rm -f "$switch_to_sessions_file" 2> /dev/null || true
    run_popup "$ps_h" "$ps_w" "$session_dir/pick_session.sh"
  fi
done
