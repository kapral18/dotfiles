#!/usr/bin/env bash
set -euo pipefail

sel_file="${1:-}"
mode="${2:-}"
query="${3:-}"
items_cmd="$HOME/.config/tmux/scripts/pickers/session/items.sh"

if [ -z "$sel_file" ] || [ ! -f "$sel_file" ] || [ ! -x "$items_cmd" ]; then
  exec "$items_cmd"
fi

script_dir="$(cd "$(dirname "$0")" && pwd)"

PYTHONPATH="$script_dir/lib:${PYTHONPATH:-}" python3 -u "$script_dir/lib/items_hide_selected_main.py" "$sel_file" "$items_cmd" "$mode" "$query"
