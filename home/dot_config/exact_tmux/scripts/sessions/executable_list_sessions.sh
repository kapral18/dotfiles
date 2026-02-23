#!/usr/bin/env bash
set -euo pipefail

session_list() {
  tmux list-sessions -F "#{session_name}"
}

output_height() {
  local list="$1"
  echo "$list" | wc -l | tr -d ' '
}

get_column_number() {
  local output_height="$1"
  local pane_height="$2"
  local columns
  columns="$(expr "${output_height}" / "${pane_height}")"
  if [ "$(expr "${output_height}" % "${pane_height}")" -gt 0 ]; then
    columns="$(expr "${columns}" + 1)"
  fi
  echo "${columns}"
}

get_column_width() {
  declare -a session_array=("${!1}")
  local width=0
  local session_name=""
  for session_name in "${session_array[@]}"; do
    if [ "${#session_name}" -gt "${width}" ]; then
      width="${#session_name}"
    fi
  done
  echo $((width + 2))
}

print_multi_column_output() {
  local output_height="$1"
  local pane_height="$2"
  local pane_width="$3"
  local columns
  columns="$(get_column_number "${output_height}" "${pane_height}")"

  # shellcheck disable=SC2086
  eval session_array=( $(tmux list-sessions -F "'#{session_name}'") )
  local width
  width="$(get_column_width session_array[@])"

  local max_columns=$(( (pane_width + 2) / width ))
  if [ "${columns}" -gt "${max_columns}" ]; then
    columns="${max_columns}"
    session_array[$((pane_height * columns - 1))]="..."
  fi

  local first_arg=''
  local arg_list=''
  local i=1
  while [ "${i}" -lt "${columns}" ]; do
    first_arg+="%-${width}s"
    arg_list+=" \"\${session_array[\$((index + $((i * pane_height)) ))]}\""
    i=$((i + 1))
  done

  local print_string=''
  print_string+='printf "'
  print_string+="${first_arg}"
  print_string+='%s\n" "${session_array[$index]}"'
  print_string+="${arg_list}"

  local index=0
  while [ "${index}" -lt "${pane_height}" ]; do
    eval "${print_string}"
    index=$((index + 1))
  done
}

main() {
  local pane_height
  pane_height="$(tmux display-message -p -F "#{pane_height}")"
  local pane_width
  pane_width="$(tmux display-message -p -F "#{pane_width}")"
  local sessions
  sessions="$(session_list)"
  local out_height
  out_height="$(output_height "${sessions}")"

  if [ "${out_height}" -gt "${pane_height}" ]; then
    print_multi_column_output "${out_height}" "${pane_height}" "${pane_width}"
  else
    echo "${sessions}"
  fi
}
main
