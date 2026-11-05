#!/usr/bin/env bash
set -euo pipefail

matches_file="${1:-}"
[ -f "$matches_file" ] || exit 0
cursor="${FZF_POS:-1}"
[ "$cursor" -ge 1 ] 2> /dev/null || exit 0
script_dir="$(cd "$(dirname "$0")" && pwd)"
python3 "$script_dir/gh_picker_mark_subtree.py" "$cursor" < "$matches_file"
