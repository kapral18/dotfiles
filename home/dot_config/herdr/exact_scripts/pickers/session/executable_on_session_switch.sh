#!/usr/bin/env bash
# herdr plugin hook for workspace.focused: record the focused workspace's
# directory as a frecency access so the picker orders rows by usage.
set -euo pipefail
# shellcheck source=../lib/herdr_ws.sh
. "$HOME/.config/herdr/scripts/pickers/lib/herdr_ws.sh"

ws_id="$(jq -r '.data.workspace_id // empty' <<< "${HERDR_PLUGIN_EVENT_JSON:-null}")"
[ -n "$ws_id" ] || exit 0
path="$(_comma_w_workspace_list | awk -F'\t' -v id="$ws_id" '$3 == id { print $2; exit }')"
[ -n "$path" ] || exit 0

lib_dir="$HOME/.config/herdr/scripts/pickers/session/lib"
PYTHONPATH="$lib_dir:${PYTHONPATH:-}" python3 -c 'import sys, frecency; frecency.add(sys.argv[1])' "$path"
