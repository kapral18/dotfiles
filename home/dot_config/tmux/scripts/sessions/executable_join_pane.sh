#!/usr/bin/env bash
set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SECONDARY_KEY_TABLE="${1:-}"
BREAK_PANE_FLAG="${2:-}"
JOIN_PANE_FLAG="${3:-}"

join_pane() {
  local join_pane_flag="$1"
  tmux join-pane "${join_pane_flag}" || tmux display-message "Mark a(nother) pane first"

  if [ "${BREAK_PANE_FLAG}" == "${join_pane_flag}" ]; then
    tmux break-pane || true
  fi
}

main() {
  if [ -z "${JOIN_PANE_FLAG}" ]; then
    tmux switch-client -T"${SECONDARY_KEY_TABLE}"
  else
    join_pane "${JOIN_PANE_FLAG}"
  fi
}
main
