#!/usr/bin/env bash
# tmux popup wrapper for the GitHub picker.
# Launched by prefix+G (replaces gh-dash popup).
set -euo pipefail

session_dir="$HOME/.config/tmux/scripts/pickers/session"
github_dir="$HOME/.config/tmux/scripts/pickers/github"
lib_dir="$HOME/.config/tmux/scripts/pickers/lib"
handoff_namespace="$lib_dir/handoff_namespace.py"
ralph_apply_cmd="$lib_dir/handoff_to_ralph_apply.sh"

# One random handoff namespace owns this whole outer popup loop. Its token is
# exported and injected into every child popup with `display-popup -e`, so the
# GH <-> session pivots and the GH -> Ralph hand-off share one private
# pin/sentinel space and can never read, clear, or consume another popup loop's
# state. The owner removes the namespace on EXIT.
token="$("$handoff_namespace" begin --owner-pid "$$" --owner-role popup-loop --entry gh-popup)" || {
  tmux display-message "picker handoff: unavailable" 2> /dev/null || true
  exit 1
}
export TMUX_PICKER_HANDOFF_TOKEN="$token"
# Every exit ends (removes) this namespace by owner pid. The Ralph hand-off no
# longer needs the namespace to outlive the wrapper: handoff_to_ralph_apply.sh
# retains a lifecycle-managed 0600 copy of the context under the handoff root
# before queuing its asynchronous command-prompt, so the deferred `,ralph go`
# run reads that retained copy rather than this namespace's context sibling.
_gh_popup_cleanup() {
  "$handoff_namespace" end --owner-pid "$$" --token "$TMUX_PICKER_HANDOFF_TOKEN" 2> /dev/null || true
}
trap _gh_popup_cleanup EXIT

ralph_pin_file="$("$handoff_namespace" path gh_picker_ralph_pin)"
switch_sessions_file="$("$handoff_namespace" path gh_picker_switch_sessions)"
session_switch_gh_file="$("$handoff_namespace" path pick_session_switch_gh)"

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

run_popup() {
  local h="$1" w="$2" cmd="$3"
  tmux set-option -g default-shell /bin/sh \; \
    display-popup -E \
    -e "TMUX_PICKER_HANDOFF_TOKEN=$TMUX_PICKER_HANDOFF_TOKEN" \
    -h "${h}%" -w "${w}%" -d "#{pane_current_path}" "$cmd" \; \
    set-option -g default-shell "$orig_shell" 2> /dev/null || true
}

while true; do
  run_popup "$gh_h" "$gh_w" "$github_dir/gh_dashboard.sh"

  if [ -f "$ralph_pin_file" ]; then
    "$ralph_apply_cmd" "$ralph_pin_file" || true
    break
  fi

  if [ -f "$switch_sessions_file" ]; then
    rm -f "$switch_sessions_file" 2> /dev/null || true
    run_popup "$ps_h" "$ps_w" "$session_dir/pick_session.sh"

    if [ -f "$session_switch_gh_file" ]; then
      rm -f "$session_switch_gh_file" 2> /dev/null || true
      continue
    fi
  fi

  break
done
