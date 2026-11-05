#!/usr/bin/env bash
set -euo pipefail

herdr="${HERDR_BIN_PATH:-herdr}"
state="${HERDR_PLUGIN_STATE_DIR:?}/history"

case "${1:-}" in
  record)
    focused="$(jq -r '.data.workspace_id // empty' <<< "${HERDR_PLUGIN_EVENT_JSON:-null}")"
    [ -n "$focused" ] || exit 0
    current="$(sed -n 1p "$state" 2> /dev/null || true)"
    [ "$focused" != "$current" ] || exit 0
    printf '%s\n%s\n' "$focused" "$current" > "$state.tmp"
    mv "$state.tmp" "$state"
    ;;
  last)
    previous="$(sed -n 2p "$state" 2> /dev/null || true)"
    [ -n "$previous" ] || exit 0
    "$herdr" workspace focus "$previous" > /dev/null
    ;;
  *)
    exit 2
    ;;
esac
