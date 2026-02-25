#!/usr/bin/env bash
set -euo pipefail

tmux_opt() {
  local key="$1"
  local default_value="$2"
  local value=""
  if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
    value="$(tmux show-option -gqv "${key}" 2>/dev/null || true)"
  fi
  if [ -n "$value" ]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$default_value"
  fi
}

mtime_epoch() {
  local f="$1"
  if [ ! -f "$f" ]; then
    printf '0\n'
    return 0
  fi
  if stat -c %Y "$f" >/dev/null 2>&1; then
    stat -c %Y "$f"
    return 0
  fi
  stat -f %m "$f"
}

post_action() {
  local action="$1"
  local -a hdr=()
  if [ -n "${FZF_API_KEY:-}" ]; then
    hdr+=(-H "x-api-key: ${FZF_API_KEY}")
  fi
  if [ -n "${FZF_SOCK:-}" ]; then
    curl --silent --show-error --fail --unix-socket "$FZF_SOCK" \
      -X POST http://localhost \
      "${hdr[@]}" \
      --data "$action" >/dev/null 2>&1
    return $?
  fi
  if [ -n "${FZF_PORT:-}" ]; then
    curl --silent --show-error --fail \
      -X POST "http://127.0.0.1:${FZF_PORT}" \
      "${hdr[@]}" \
      --data "$action" >/dev/null 2>&1
    return $?
  fi
  return 1
}

fzf_alive() {
  local -a hdr=()
  if [ -n "${FZF_API_KEY:-}" ]; then
    hdr+=(-H "x-api-key: ${FZF_API_KEY}")
  fi
  if [ -n "${FZF_SOCK:-}" ]; then
    curl --silent --show-error --fail --unix-socket "$FZF_SOCK" \
      "${hdr[@]}" http://localhost >/dev/null 2>&1
    return $?
  fi
  if [ -n "${FZF_PORT:-}" ]; then
    curl --silent --show-error --fail \
      "${hdr[@]}" "http://127.0.0.1:${FZF_PORT}" >/dev/null 2>&1
    return $?
  fi
  return 1
}

fzf_state_json() {
  local -a hdr=()
  if [ -n "${FZF_API_KEY:-}" ]; then
    hdr+=(-H "x-api-key: ${FZF_API_KEY}")
  fi
  if [ -n "${FZF_SOCK:-}" ]; then
    curl --silent --show-error --fail --unix-socket "$FZF_SOCK" \
      "${hdr[@]}" "http://localhost?limit=5000" 2>/dev/null
    return $?
  fi
  if [ -n "${FZF_PORT:-}" ]; then
    curl --silent --show-error --fail \
      "${hdr[@]}" "http://127.0.0.1:${FZF_PORT}?limit=5000" 2>/dev/null
    return $?
  fi
  return 1
}

fzf_has_selected_matches() {
  local state="${1:-}"
  if [ -z "$state" ]; then
    state="$(fzf_state_json 2>/dev/null || true)"
  fi
  [ -n "$state" ] || return 1
  # GET state includes per-match `"selected":true|false`; if any visible match
  # is selected, defer background reload to preserve multi-selection.
  printf '%s' "$state" | grep -q '"selected"[[:space:]]*:[[:space:]]*true'
}

fzf_has_nonempty_query() {
  local state="${1:-}"
  if [ -z "$state" ]; then
    state="$(fzf_state_json 2>/dev/null || true)"
  fi
  [ -n "$state" ] || return 1
  printf '%s' "$state" | grep -q '"query"[[:space:]]*:'
  if printf '%s' "$state" | grep -q '"query"[[:space:]]*:[[:space:]]*""'; then
    return 1
  fi
  return 0
}

once=0
force=0

while [ $# -gt 0 ]; do
  case "$1" in
  --once) once=1 ;;
  --force) force=1 ;;
  esac
  shift
done

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
update_cmd="$HOME/.config/tmux/scripts/pick_session_index_update.sh"
items_cmd="$HOME/.config/tmux/scripts/pick_session_items.sh"

[ -x "$update_cmd" ] || exit 0
[ -x "$items_cmd" ] || exit 0
command -v curl >/dev/null 2>&1 || exit 0

interval_ms="$(tmux_opt '@pick_session_live_refresh_interval_ms' '1500')"
live_ttl="$(tmux_opt '@pick_session_live_refresh_ttl' '20')"
pause_on_multi="$(tmux_opt '@pick_session_live_refresh_pause_on_multi' 'on')"
pause_on_query="$(tmux_opt '@pick_session_live_refresh_pause_on_query' 'on')"
start_delay_ms="$(tmux_opt '@pick_session_live_refresh_start_delay_ms' '5000')"
case "$interval_ms" in
'' | *[!0-9]*) interval_ms=1500 ;;
esac
case "$live_ttl" in
'' | *[!0-9]*) live_ttl=20 ;;
esac
case "$start_delay_ms" in
'' | *[!0-9]*) start_delay_ms=5000 ;;
esac

sleep_s="0.5"
if [ "$interval_ms" -ge 1000 ]; then
  sleep_s="$((interval_ms / 1000)).$((interval_ms % 1000))"
else
  sleep_s="0.$(printf '%03d' "$interval_ms")"
fi

run_update() {
  local -a args=(--quiet)
  if [ "$force" -eq 1 ]; then
    args+=(--force)
  elif [ -n "$live_ttl" ]; then
    args+=("--ttl=${live_ttl}")
  fi
  "$update_cmd" "${args[@]}" >/dev/null 2>&1 || true
}

run_update_quick_only() {
  local -a args=(--quiet --quick-only)
  if [ "$force" -eq 1 ]; then
    args+=(--force)
  elif [ -n "$live_ttl" ]; then
    args+=("--ttl=${live_ttl}")
  fi
  "$update_cmd" "${args[@]}" >/dev/null 2>&1 || true
}

maybe_reload_on_change() {
  local before="$1"
  local after
  local state=""
  local need_state=0
  after="$(mtime_epoch "$cache_file" 2>/dev/null || printf '0')"
  if [ "$after" = "$before" ]; then
    printf '%s\n' "$after"
    return 0
  fi

  case "$pause_on_multi" in
  1 | true | yes | on) need_state=1 ;;
  esac
  case "$pause_on_query" in
  1 | true | yes | on) need_state=1 ;;
  esac

  if [ "$need_state" -eq 1 ]; then
    state="$(fzf_state_json 2>/dev/null || true)"
  fi

  case "$pause_on_multi" in
  1 | true | yes | on)
    if fzf_has_selected_matches "$state"; then
      # Keep the old mtime so we retry this reload once selection is cleared.
      printf '%s\n' "$before"
      return 0
    fi
    ;;
  esac

  case "$pause_on_query" in
  1 | true | yes | on)
    if fzf_has_nonempty_query "$state"; then
      # Keep the old mtime so we retry this reload once the user clears query.
      printf '%s\n' "$before"
      return 0
    fi
    ;;
  esac

  post_action "reload($items_cmd)" || return 1
  printf '%s\n' "$after"
}

prev_mtime="$(mtime_epoch "$cache_file" 2>/dev/null || printf '0')"
if [ "$once" -ne 1 ] && [ "$start_delay_ms" -gt 0 ]; then
  if [ "$start_delay_ms" -ge 1000 ]; then
    sleep "$((start_delay_ms / 1000)).$((start_delay_ms % 1000))"
  else
    sleep "0.$(printf '%03d' "$start_delay_ms")"
  fi
fi

# Startup path should be lightweight so opening the picker is not competing
# with a full reindex. Manual `--once` refresh (alt-r) remains a full refresh.
if [ "$once" -eq 1 ]; then
  run_update
else
  run_update_quick_only
fi
prev_mtime="$(maybe_reload_on_change "$prev_mtime")" || exit 0

[ "$once" -eq 1 ] && exit 0

while :; do
  fzf_alive || exit 0
  sleep "$sleep_s"
  run_update
  prev_mtime="$(maybe_reload_on_change "$prev_mtime")" || exit 0
done
