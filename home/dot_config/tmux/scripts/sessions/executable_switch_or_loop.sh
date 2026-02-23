#!/usr/bin/env bash
set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SESSION_NAME="${1:-}"

source "${CURRENT_DIR}/helpers.sh"

dismiss_session_list_page_from_view() {
  tmux send-keys C-c
}

session_name_not_provided() {
  [ -z "${SESSION_NAME}" ]
}

main() {
  if session_name_not_provided; then
    dismiss_session_list_page_from_view
    exit 0
  fi

  if session_exists_prefix; then
    dismiss_session_list_page_from_view
    tmux switch-client -t "${SESSION_NAME}"
  else
    tmux command-prompt -p session: "run-shell -b '${CURRENT_DIR}/switch_or_loop.sh \"%%\"'"
  fi
}
main
