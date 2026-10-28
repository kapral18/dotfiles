#!/usr/bin/env bash
# ctrl-t handler for the GH picker. Snapshots the fzf multi-selection to a
# unique cache path (dropping header rows), then runs the batch worktree
# creator on that snapshot.
#
#
# Dispatch is synchronous (`exec`) because gh_batch_worktree.sh's foreground
# phase opens `$EDITOR` for issue branch naming and needs the user's TTY.
# After naming, the script itself detaches a nohup background job so clones
# survive closing the dashboard popup.
#
# Usage: gh_picker_ctrl_t.sh <fzf-selection-file> <batch_worktree_cmd>
set -euo pipefail

sel_in="${1:-}"
batch_cmd="${2:-}"

[ -n "$sel_in" ] && [ -f "$sel_in" ] || exit 0
[ -n "$batch_cmd" ] && [ -x "$batch_cmd" ] || exit 0

snap_cmd="$HOME/.config/tmux/scripts/pickers/lib/snapshot_fzf_selection.sh"
snap="$("$snap_cmd" --filter-awk '$2 != "header"' "$sel_in")" || exit 0
[ -n "$snap" ] || exit 0
exec "$batch_cmd" "$snap"
