#!/usr/bin/env bash
# herdr plugin hook for the workspace path registry. No argument (workspace.closed,
# or startup with no event): drop rows of closed workspaces so a reissued id
# never inherits a directory; startup catches closes whose event was lost.
# `relabel` (workspace.renamed): keep the row under the workspace's new label.
set -euo pipefail
# shellcheck source=../lib/herdr_ws.sh
. "$HOME/.config/herdr/scripts/pickers/lib/herdr_ws.sh"

ws_id="$(jq -r '.data.workspace_id // empty' <<< "${HERDR_PLUGIN_EVENT_JSON:-null}")"
if [ "${1:-}" = relabel ]; then
  _comma_w_relabel_workspace "$ws_id"
else
  # At startup the listing must succeed, or no stale row would be dropped.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -n "$ws_id" ] || _comma_w_herdr workspace list > /dev/null 2>&1 && break
    sleep 0.5
  done
  _comma_w_prune_workspace_registry "$ws_id"
fi
