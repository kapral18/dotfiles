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
  [ -f "$f" ] || {
    printf '0\n'
    return 0
  }
  if stat -c %Y "$f" >/dev/null 2>&1; then
    stat -c %Y "$f"
    return 0
  fi
  stat -f %m "$f"
}

live_refresh_cmd="$HOME/.config/tmux/scripts/pick_session_live_refresh.sh"
items_cmd="$HOME/.config/tmux/scripts/pick_session_items.sh"
filter_cmd="$HOME/.config/tmux/scripts/pick_session_filter.sh"
reload_cmd="$HOME/.config/tmux/scripts/pick_session_fzf_reload.sh"
ordered_update_cmd="$HOME/.config/tmux/scripts/pick_session_ordered_cache_update.sh"

if [ ! -x "$filter_cmd" ]; then
  filter_cmd="$items_cmd"
fi

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
ordered_file="${cache_dir}/pick_session_items_ordered.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"

cache_mt="$(mtime_epoch "$cache_file" 2>/dev/null || printf '0')"
ordered_mt="$(mtime_epoch "$ordered_file" 2>/dev/null || printf '0')"
mutation_mt="$(mtime_epoch "$mutation_file" 2>/dev/null || printf '0')"
pending_mt="$(mtime_epoch "$pending_file" 2>/dev/null || printf '0')"
ordered_fresh=0
if [ -s "$ordered_file" ] && [ "$ordered_mt" -ge "$cache_mt" ] && [ "$ordered_mt" -ge "$mutation_mt" ] && [ "$ordered_mt" -ge "$pending_mt" ]; then
  ordered_fresh=1
fi

if [ "$ordered_fresh" -ne 1 ] && [ -x "$ordered_update_cmd" ] && [ -s "$cache_file" ]; then
  "$ordered_update_cmd" --quiet >/dev/null 2>&1 &
fi

reorder_after_open="$(tmux_opt '@pick_session_reorder_after_open' 'on')"
reorder_delay_ms="$(tmux_opt '@pick_session_reorder_after_open_delay_ms' '180')"
case "$reorder_delay_ms" in
'' | *[!0-9]*) reorder_delay_ms=180 ;;
esac

case "$reorder_after_open" in
1 | true | yes | on)
  if [ "$ordered_fresh" -ne 1 ] && [ -x "$reload_cmd" ]; then
    "$reload_cmd" "$filter_cmd --force-order" "$reorder_delay_ms" >/dev/null 2>&1 &
  fi
  ;;
esac

live_refresh_on_start="$(tmux_opt '@pick_session_live_refresh_on_start' 'off')"
case "$live_refresh_on_start" in
1 | true | yes | on)
  if [ -x "$live_refresh_cmd" ]; then
    "$live_refresh_cmd" >/dev/null 2>&1 &
  fi
  ;;
esac
