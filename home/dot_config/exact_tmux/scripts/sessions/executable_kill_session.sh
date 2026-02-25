#!/usr/bin/env bash
set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${CURRENT_DIR}/helpers.sh"

CURRENT_SESSION_ID="${1:-}"

switch_to_next_session() {
  tmux switch-client -n 2>/dev/null || true
}

switch_to_alternate_session() {
  tmux switch-client -l 2>/dev/null || true
}

alternate_session_name() {
  tmux display-message -p "#{client_last_session}"
}

current_session_name() {
  tmux display-message -p "#{client_session}"
}

number_of_sessions() {
  tmux list-sessions | wc -l | tr -d ' '
}

switch_session() {
  local alt
  alt="$(alternate_session_name)"

  if [ "$(number_of_sessions)" -eq 1 ]; then
    return 0
  elif [ -z "${alt}" ]; then
    switch_to_next_session
  elif [ "${alt}" == "$(current_session_name)" ]; then
    switch_to_next_session
  else
    # `client_last_session` can be stale (session was killed/renamed elsewhere).
    # Don't fail the entire kill flow if we can't switch to it.
    if tmux has-session -t "${alt}" 2>/dev/null; then
      switch_to_alternate_session
    else
      switch_to_next_session
    fi
  fi
}

kill_current_session() {
  [ -n "${CURRENT_SESSION_ID}" ] || return 0
  if ! tmux has-session -t "${CURRENT_SESSION_ID}" 2>/dev/null; then
    return 0
  fi
  tmux kill-session -t "${CURRENT_SESSION_ID}" 2>/dev/null || true
}

main() {
  switch_session
  kill_current_session
}
main
