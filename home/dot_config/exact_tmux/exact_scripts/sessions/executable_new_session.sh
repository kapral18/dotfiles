#!/usr/bin/env bash
set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SESSION_NAME="${1:-}"

source "${CURRENT_DIR}/helpers.sh"

session_name_not_provided() {
  [ -z "${SESSION_NAME}" ]
}

create_new_tmux_session() {
  if session_name_not_provided; then
    exit 0
  elif session_exists_exact; then
    switch_to_session "${SESSION_NAME}"
    display_message "Switched to existing session ${SESSION_NAME}" "2000"
  else
    # tmux may sanitize the session name (e.g. '.' -> '_'), so use the reported
    # name for switching.
    created_session_name="$(
      TMUX="" tmux -S "$(tmux_socket)" new-session -d -P -c "#{pane_current_path}" -s "${SESSION_NAME}"
    )"
    switch_to_session "${created_session_name}"
  fi
}

main() {
  create_new_tmux_session
}
main
