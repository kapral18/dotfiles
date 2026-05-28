#!/usr/bin/env bash
# Mark the cursor row + every row in the same family. Wired to `alt-M`.
#
# Args: <mode_file> <scope_file> <items_cmd>
#
# Resolves mode + scope, re-runs the items_cmd in `--cache-only` mode to obtain
# the exact TSV fzf is displaying, then asks `gh_picker_mark_subtree.py` to
# compute fzf actions. The Python helper picks the family from the cursor row
# (parent + descendants, or sibling group + parent for a child cursor) and
# emits a `pos(...)+toggle` chain so all marker positions get flipped.
#
# Loose rows, section headers, and backport placeholders produce no output;
# fzf treats that as a no-op which is the intended user experience there.
set -euo pipefail

mode_file="${1:-}"
scope_file="${2:-}"
items_cmd="${3:-}"

if [ -z "$mode_file" ] || [ -z "$scope_file" ] || [ -z "$items_cmd" ]; then
  exit 0
fi

cursor="${FZF_POS:-1}"
[ "$cursor" -ge 1 ] 2> /dev/null || exit 0

mode="$(cat "$mode_file" 2> /dev/null || echo work)"
scope="$(cat "$scope_file" 2> /dev/null || echo all)"
script_dir="$(cd "$(dirname "$0")" && pwd)"

# Re-render the post-filter+sort TSV. `--cache-only` is cheap (it just reads
# the existing on-disk cache + applies filter+sort+offsets), so we can call it
# synchronously without making the keypress feel laggy.
rendered="$(GH_PICKER_MODE="$mode" GH_PICKER_SCOPE="$scope" "$items_cmd" --cache-only 2> /dev/null || true)"
[ -n "$rendered" ] || exit 0

actions="$(printf '%s' "$rendered" | python3 "$script_dir/gh_picker_mark_subtree.py" "$cursor" 2> /dev/null || true)"
[ -n "$actions" ] || exit 0

printf '%s' "$actions"
