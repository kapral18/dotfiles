#!/usr/bin/env bash
# ctrl-t handler for the GH picker. Filters out header rows from the fzf
# multi-selection, snapshots the result to a unique cache path, and dispatches
# the batch worktree creator on that snapshot.
#
# The previous binding wrote directly into a shared `gh_picker_multi.tsv`,
# which raced with itself across rapid keypresses (and across concurrent
# pickers). Each invocation now mints its own snapshot, so dispatches are
# fully isolated. The batch worktree creator's background phase is the last
# consumer and is responsible for unlinking the snapshot.
#
# Usage: gh_picker_ctrl_t.sh <fzf-selection-file> <batch_worktree_cmd>
set -euo pipefail

sel_in="${1:-}"
batch_cmd="${2:-}"

[ -n "$sel_in" ] && [ -f "$sel_in" ] || exit 0
[ -n "$batch_cmd" ] && [ -x "$batch_cmd" ] || exit 0

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
mkdir -p "$cache_dir" 2> /dev/null || true
snap="$(mktemp "${cache_dir}/gh_batch_worktree_sel.XXXXXX")"
awk -F $'\t' '$2 != "header"' "$sel_in" > "$snap" 2> /dev/null || true
"$batch_cmd" "$snap"
