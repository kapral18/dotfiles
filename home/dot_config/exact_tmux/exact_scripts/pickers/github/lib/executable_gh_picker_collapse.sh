#!/usr/bin/env bash
# Toggle collapse state for a parent under the cursor, or globally.
# Wired to `alt-z` (cursor toggle) and `alt-Z` (global toggle) in the picker.
#
# Args: <verb> <mode_file> <scope_file> <items_cmd>
#   verb: "toggle" or "global"
#
# Outputs fzf actions (transform binding). After updating the collapse state
# file, emits a reload that re-runs `--cache-only` so the picker reflects the
# new state immediately, plus an `execute-silent` toast so the user knows
# what happened.
#
# Cursor toggle (`alt-z`):
#   - If cursor is on a parent: toggle that parent's id in the set.
#   - If cursor is on a child: toggle the child's parent.
#   - Otherwise: no-op.
#
# Global toggle (`alt-Z`):
#   - If any currently-visible parent is collapsed, expand them all.
#   - Otherwise, collapse every visible parent that has at least one child.
set -euo pipefail

verb="${1:-}"
mode_file="${2:-}"
scope_file="${3:-}"
items_cmd="${4:-}"

if [ -z "$verb" ] || [ -z "$mode_file" ] || [ -z "$scope_file" ] || [ -z "$items_cmd" ]; then
  exit 0
fi

mode="$(cat "$mode_file" 2> /dev/null || echo work)"
scope="$(cat "$scope_file" 2> /dev/null || echo all)"
cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
state_file="${cache_dir}/gh_picker_collapsed_${mode}"
mkdir -p "$cache_dir" 2> /dev/null || true

script_dir="$(cd "$(dirname "$0")" && pwd)"
collapse_py="$script_dir/gh_picker_collapse.py"

rendered_tmp=""
cleanup() {
  [ -z "$rendered_tmp" ] || rm -f "$rendered_tmp" 2> /dev/null || true
}
trap cleanup EXIT

# Snapshot the post-filter+sort TSV once so cursor/global toggles both work off
# the same view. Re-running --cache-only twice would race against an in-flight
# bg fetch updating the cache mid-snapshot.
rendered_tmp="$(mktemp -t gh_picker_collapse_view.XXXXXX 2> /dev/null || true)"
if [ -n "$rendered_tmp" ]; then
  GH_PICKER_MODE="$mode" GH_PICKER_SCOPE="$scope" "$items_cmd" --cache-only > "$rendered_tmp" 2> /dev/null || true
fi

case "$verb" in
  toggle)
    cursor="${FZF_POS:-1}"
    parent_id=""
    if [ -n "$rendered_tmp" ] && [ -s "$rendered_tmp" ]; then
      # awk picks the row, returns either kind:repo:num (if cursor is on a
      # parent) or the parent_id field (if cursor is on a child). Loose rows
      # and headers produce empty output, which the python helper short-
      # circuits as a no-op.
      parent_id="$(awk -F '\t' -v r="$cursor" '
        NR == r {
          role = $13
          if (role == "parent") {
            kind = $2; repo = $3; num = $4
            if (kind != "" && kind != "header" && repo != "" && num != "") {
              print kind ":" repo ":" num
            }
          } else if (role == "child") {
            print $12
          }
        }' "$rendered_tmp")"
    fi
    if [ -z "$parent_id" ]; then
      tmux display-message "collapse: no parent under cursor" 2> /dev/null || true
      exit 0
    fi
    python3 "$collapse_py" toggle "$state_file" "$parent_id" 2> /dev/null || true
    ;;
  global)
    if [ -z "$rendered_tmp" ] || [ ! -s "$rendered_tmp" ]; then
      exit 0
    fi
    python3 "$collapse_py" global-toggle "$state_file" "$rendered_tmp" 2> /dev/null || true
    ;;
  *)
    exit 0
    ;;
esac

reload_cmd="GH_PICKER_MODE=$(printf %q "$mode") GH_PICKER_SCOPE=$(printf %q "$scope") $(printf %q "$items_cmd") --cache-only 2>/dev/null"
printf 'reload(%s)+track' "$reload_cmd"
