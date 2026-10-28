#!/usr/bin/env bash
# Mark the cursor row + every row in the same family. Wired to `alt-M`.
#
# Args: <scope_file> <items_cmd>
#
set -euo pipefail

scope_file="${1:-}"
items_cmd="${2:-}"

if [ -z "$scope_file" ] || [ -z "$items_cmd" ]; then
  exit 0
fi

cursor="${FZF_POS:-1}"
[ "$cursor" -ge 1 ] 2> /dev/null || exit 0

scope="$(cat "$scope_file" 2> /dev/null || echo all)"
script_dir="$(cd "$(dirname "$0")" && pwd)"

rendered="$(GH_PICKER_SCOPE="$scope" "$items_cmd" --cache-only 2> /dev/null || true)"
[ -n "$rendered" ] || exit 0

actions="$(printf '%s' "$rendered" | python3 "$script_dir/gh_picker_mark_subtree.py" "$cursor" 2> /dev/null || true)"
[ -n "$actions" ] || exit 0

printf '%s' "$actions"
