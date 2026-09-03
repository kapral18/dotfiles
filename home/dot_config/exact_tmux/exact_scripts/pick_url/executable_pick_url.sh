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

# When the pane is scrolled back in copy mode, capture-pane without -S/-E
# returns the live bottom screen, not the lines the user is looking at.
# Shift the range so the scrolled viewport is what gets scanned. Only copy-mode
# offsets map onto the pane's scrollback; other modes (view-mode, tree-mode)
# draw their own screen, so they keep the plain capture.
scroll_position=0
pane_height=0
IFS='|' read -r pane_mode scroll_position pane_height <<< "$(tmux display-message -p '#{pane_mode}|#{scroll_position}|#{pane_height}')"
if [[ "${pane_mode:-}" != 'copy-mode' || ! "${scroll_position:-}" =~ ^[0-9]+$ || ! "${pane_height:-}" =~ ^[0-9]+$ ]]; then
  scroll_position=0
fi

capture_flags=()
if [[ "${limit}" == 'screen' ]]; then
  if ((scroll_position > 0)); then
    capture_flags=(-S "-${scroll_position}" -E "$((pane_height - scroll_position - 1))")
  fi
elif [[ "${limit}" =~ ^[0-9]+$ ]] && ((scroll_position > limit)); then
  capture_flags=(-S "-${scroll_position}")
else
  capture_flags=(-S "-${limit}")
fi
items="$(tmux capture-pane -J -p -e ${capture_flags[@]+"${capture_flags[@]}"} | python3 "$script_dir/lib/strip_cr.py" --extract-candidates --extra-filter "${extra_filter}" | nl -w3 -s '  ')"

if [[ -z "${items}" ]]; then
  tmux display-message 'tmux: no URLs found'
  exit 0
fi

selected="$(fzf_filter <<< "${items}" || true)"
if [[ -z "${selected}" ]]; then
  exit 0
fi

echo "${selected}" | sed -E 's/^[[:space:]]*[0-9]+[[:space:]]+//' | while IFS= read -r chosen; do
  [[ -n "${chosen}" ]] && open_url "${chosen}" &> "/tmp/tmux-$(id -u)-pick-url.log"
done
