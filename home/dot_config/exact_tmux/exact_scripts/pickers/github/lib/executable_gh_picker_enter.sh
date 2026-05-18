#!/usr/bin/env bash
# Enter-key handler for the GH picker.
# Decides between in-place batch worktree creation (when items are marked)
# and single-item accept (which the outer picker dispatches via gh_action.sh).
#
# Marked-count is derived from {+f}: fzf writes the marked rows to that file,
# falling back to the current row when nothing is marked. We treat >1 lines
# as "the user marked items", which matches the documented "enter=checkout
# (batch if marked)" contract advertised in the picker header, keyhelp, and
# docs/topics/workflow/tmux/pickers.md.
#
# Snapshotting goes through the shared `snapshot_fzf_selection.sh` helper so
# the per-binding mktemp lifecycle is consistent with gh ctrl-t and the
# session picker's dispatch primitive. The batch worktree creator's
# background phase unlinks the snapshot when it's done.
#
# Usage: gh_picker_enter.sh <kind> <selection_file> <batch_wt_cmd>
#
# Outputs an fzf action string to stdout (consumed by `--bind enter:transform`).
set -uo pipefail

kind="${1:-}"
selection_file="${2:-}"
batch_wt_cmd="${3:-}"

count=0
if [ -n "$selection_file" ] && [ -f "$selection_file" ]; then
  count="$(wc -l < "$selection_file" 2> /dev/null | tr -d ' ' || echo 0)"
fi

if [ "${count:-0}" -gt 1 ] && [ -n "$batch_wt_cmd" ]; then
  snap_cmd="$HOME/.config/tmux/scripts/pickers/lib/snapshot_fzf_selection.sh"
  snap="$("$snap_cmd" --filter-awk '$2 != "header"' "$selection_file" 2> /dev/null || true)"
  if [ -n "$snap" ]; then
    printf 'execute(%s %s)+deselect-all+refresh-preview' \
      "$(printf %q "$batch_wt_cmd")" "$(printf %q "$snap")"
    exit 0
  fi
fi

if [ "$kind" = "header" ]; then
  printf 'down'
  exit 0
fi

printf 'accept'
