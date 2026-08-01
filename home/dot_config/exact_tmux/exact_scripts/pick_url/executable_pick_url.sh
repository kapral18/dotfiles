#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"

die() {
  tmux display-message "$1"
  exit 0
}

need_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" > /dev/null 2>&1; then
    die "tmux: missing command: ${cmd}"
  fi
}

tmux_opt() {
  local key="$1"
  local default_value="$2"
  local value
  value="$(tmux show -gqv "${key}")"
  if [[ -n "${value}" ]]; then
    echo "${value}"
  else
    echo "${default_value}"
  fi
}

fzf_filter() {
  local tmux_popup extra_flags cmd
  need_cmd fzf

  tmux_popup="$(tmux_opt '@pick_url_popup' 'center,100%,50%')"
  extra_flags="$(tmux_opt '@pick_url_fzf_flags' '')"

  cmd="fzf --tmux $(printf '%q' "${tmux_popup}") --multi --exit-0 --no-preview"
  if [[ -n "${extra_flags}" ]]; then
    cmd+=" ${extra_flags}"
  fi

  # shellcheck disable=SC2086
  eval "FZF_DEFAULT_OPTS='' ${cmd}"
}

extra_filter="$(tmux_opt '@pick_url_extra_filter' '')"
limit="$(tmux_opt '@pick_url_history_limit' 'screen')"
custom_open="$(tmux_opt '@pick_url_open_cmd' '')"
open_url() {
  if [[ -n "${custom_open}" ]]; then
    "${custom_open}" "$@"
  elif command -v xdg-open > /dev/null 2>&1; then
    nohup xdg-open "$@" > /dev/null 2>&1 &
  elif command -v open > /dev/null 2>&1; then
    nohup open "$@" > /dev/null 2>&1 &
  elif [[ -n "${BROWSER:-}" ]]; then
    nohup "${BROWSER}" "$@" > /dev/null 2>&1 &
  fi
}

if [[ -z "${TMUX:-}" ]]; then
  die "tmux: not running inside tmux"
fi

if [[ "${limit}" == 'screen' ]]; then
  items="$(tmux capture-pane -J -p -e | python3 "$script_dir/lib/strip_cr.py" --extract-candidates --extra-filter "${extra_filter}" | nl -w3 -s '  ')"
else
  items="$(tmux capture-pane -J -p -e -S -"${limit}" | python3 "$script_dir/lib/strip_cr.py" --extract-candidates --extra-filter "${extra_filter}" | nl -w3 -s '  ')"
fi

if [[ -z "${items}" ]]; then
  tmux display-message 'tmux: no URLs found'
  exit 0
fi

selected="$(fzf_filter <<< "${items}" || true)"
if [[ -z "${selected}" ]]; then
  exit 0
fi

echo "${selected}" | awk '{print $2}' | while read -r chosen; do
  open_url "${chosen}" &> "/tmp/tmux-$(id -u)-pick-url.log"
done
