#!/usr/bin/env bash
# herdr popup: pick a pane from another workspace and move it next to the
# active pane; $1 is the split direction (right or down, default right).
set -euo pipefail

target="${HERDR_ACTIVE_PANE_ID:-}"
tab="${HERDR_ACTIVE_TAB_ID:-}"
[ -n "$target" ] && [ -n "$tab" ] || exit 0

pick="$(
  jq -rn --arg ws "${HERDR_ACTIVE_WORKSPACE_ID:-}" \
    --argjson workspaces "$(herdr workspace list)" --argjson panes "$(herdr pane list)" '
    ($workspaces.result.workspaces | map({(.workspace_id): .label}) | add // {}) as $name
    | $panes.result.panes[] | select(.workspace_id != $ws)
    | "\(.pane_id)\t\($name[.workspace_id] // "")  \(.label // .display_agent // .agent // .terminal_title_stripped // "")  \(.cwd // "")"' \
    | fzf --delimiter='\t' --with-nth=2 --prompt 'join pane > ' --no-multi \
    || true
)"
[ -n "$pick" ] || exit 0

source="${pick%%$'\t'*}"
# herdr refuses a move whose source or target tab is zoomed. Unzooming also
# focuses the pane (and its workspace), so it runs only on a zoomed tab and
# the target goes last.
unzoom() {
  [ "$(herdr pane layout --pane "$1" | jq -r '.result.layout.zoomed')" != true ] \
    || herdr pane zoom --pane "$1" --off > /dev/null
}
unzoom "$source"
unzoom "$target"
herdr pane move "$source" --tab "$tab" --split "${1:-right}" --target-pane "$target" --focus > /dev/null
