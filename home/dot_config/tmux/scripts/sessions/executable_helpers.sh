#!/usr/bin/env bash
set -euo pipefail

get_tmux_option() {
  local option="$1"
  local default_value="$2"
  local option_value
  option_value="$(tmux show-option -gqv "$option")"
  if [[ -z "${option_value}" ]]; then
    echo "${default_value}"
  else
    echo "${option_value}"
  fi
}

display_message() {
  local message="$1"
  local display_duration="5000"
  if [[ "$#" -eq 2 ]]; then
    display_duration="$2"
  fi

  local saved_display_time
  saved_display_time="$(get_tmux_option "display-time" "750")"

  tmux set-option -gq display-time "${display_duration}"
  tmux display-message "${message}"
  tmux set-option -gq display-time "${saved_display_time}"
}

tmux_socket() {
  echo "${TMUX}" | cut -d',' -f1
}

session_exists_exact() {
  tmux has-session -t "=${SESSION_NAME}" >/dev/null 2>&1
}

session_exists_prefix() {
  tmux has-session -t "${SESSION_NAME}" >/dev/null 2>&1
}

switch_to_session() {
  local session_name="$1"
  tmux switch-client -t "${session_name}"
}
