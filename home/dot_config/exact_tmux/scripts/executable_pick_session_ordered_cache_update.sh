#!/usr/bin/env bash
set -euo pipefail

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

force=0
quiet=0
while [ $# -gt 0 ]; do
  case "$1" in
  --force) force=1 ;;
  --quiet) quiet=1 ;;
  esac
  shift
done

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
cache_file="${cache_dir}/pick_session_items.tsv"
ordered_file="${cache_dir}/pick_session_items_ordered.tsv"
mutation_file="${cache_dir}/pick_session_mutations.tsv"
pending_file="${cache_dir}/pick_session_pending.tsv"
lock_dir="${ordered_file}.lock"
mkdir -p "$cache_dir" 2>/dev/null || true

[ -s "$cache_file" ] || exit 0

cache_mt="$(mtime_epoch "$cache_file" 2>/dev/null || printf '0')"
ordered_mt="$(mtime_epoch "$ordered_file" 2>/dev/null || printf '0')"
mutation_mt="$(mtime_epoch "$mutation_file" 2>/dev/null || printf '0')"
pending_mt="$(mtime_epoch "$pending_file" 2>/dev/null || printf '0')"

if [ "$force" -ne 1 ] && [ "$ordered_mt" -gt 0 ] && [ "$ordered_mt" -ge "$cache_mt" ] && [ "$ordered_mt" -ge "$mutation_mt" ] && [ "$ordered_mt" -ge "$pending_mt" ]; then
  exit 0
fi

if ! mkdir "$lock_dir" 2>/dev/null; then
  pid_file="${lock_dir}/pid"
  if [ -f "$pid_file" ]; then
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      exit 0
    fi
  fi
  rm -rf "$lock_dir" 2>/dev/null || exit 0
  mkdir "$lock_dir" 2>/dev/null || exit 0
fi

tmp_out=""
cleanup() {
  rm -f "${tmp_out:-}" 2>/dev/null || true
  rm -f "${lock_dir}/pid" 2>/dev/null || true
  rmdir "$lock_dir" 2>/dev/null || true
}
trap cleanup EXIT
printf '%s\n' "$$" >"${lock_dir}/pid" 2>/dev/null || true

filter_cmd="$HOME/.config/tmux/scripts/pick_session_filter.sh"
items_cmd="$HOME/.config/tmux/scripts/pick_session_items.sh"
tmp_out="$(mktemp -t pick_session_items_ordered.XXXXXX)"

if [ -x "$filter_cmd" ]; then
  "$filter_cmd" --force-order >"$tmp_out" 2>/dev/null || true
elif [ -x "$items_cmd" ]; then
  "$items_cmd" >"$tmp_out" 2>/dev/null || true
fi

[ -s "$tmp_out" ] || exit 0
mv -f "$tmp_out" "$ordered_file"

if [ "$quiet" -ne 1 ] && command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux display-message -d 1200 "pick_session: ordered cache updated" 2>/dev/null || true
fi
