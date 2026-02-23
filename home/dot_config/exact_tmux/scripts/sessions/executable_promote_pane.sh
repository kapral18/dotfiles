#!/usr/bin/env bash
set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${CURRENT_DIR}/helpers.sh"

CURRENT_SESSION_NAME="${1:-}"
CURRENT_PANE_ID="${2:-}"
PANE_CURRENT_PATH="${3:-}"

number_of_panes() {
  tmux list-panes -s -t "${CURRENT_SESSION_NAME}" | wc -l | tr -d ' '
}

create_new_session() {
  TMUX="" tmux -S "$(tmux_socket)" new-session -c "${PANE_CURRENT_PATH}" -d -P -F "#{session_name}"
}

new_session_pane_id() {
  local session_name="$1"
  tmux list-panes -t "${session_name}" -F "#{pane_id}"
}

promote_pane() {
  local session_name
  session_name="$(create_new_session)"
  local new_pane_id
  new_pane_id="$(new_session_pane_id "${session_name}")"
  tmux join-pane -s "${CURRENT_PANE_ID}" -t "${new_pane_id}"
  tmux kill-pane -t "${new_pane_id}"
  switch_to_session "${session_name}"
}

main() {
  if [ "$(number_of_panes)" -gt 1 ]; then
    promote_pane
  else
    display_message "Can't promote with only one pane in session"
  fi
}
main
