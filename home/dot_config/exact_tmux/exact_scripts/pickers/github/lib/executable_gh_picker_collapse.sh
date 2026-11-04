#!/usr/bin/env bash
# Toggle collapse state for a parent under the cursor, or globally.
# Wired to `alt-z` (cursor toggle) and `alt-Z` (global toggle) in the picker.
#
# Args: <verb> <scope_file> <items_cmd> <matches_file>
#   verb: "toggle" or "global"
#
set -euo pipefail

verb="${1:-}"
scope_file="${2:-}"
items_cmd="${3:-}"
rendered_tmp="${4:-}"

if [ -z "$verb" ] || [ -z "$scope_file" ] || [ -z "$items_cmd" ]; then
  exit 0
fi

scope="$(cat "$scope_file" 2> /dev/null || echo all)"
cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
state_file="${cache_dir}/gh_picker_collapsed"
mkdir -p "$cache_dir" 2> /dev/null || true

script_dir="$(cd "$(dirname "$0")" && pwd)"
collapse_py="$script_dir/gh_picker_collapse.py"

[ -f "$rendered_tmp" ] || exit 0

case "$verb" in
  toggle)
    cursor="${FZF_POS:-1}"
    parent_id=""
    if [ -n "$rendered_tmp" ] && [ -s "$rendered_tmp" ]; then
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

reload_cmd="GH_PICKER_SCOPE=$(printf %q "$scope") $(printf %q "$items_cmd") --cache-only 2>/dev/null"
printf 'reload(%s)+track' "$reload_cmd"
