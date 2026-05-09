#!/usr/bin/env bash
set -euo pipefail

target="${1:-}"
stop_at="${2:-$HOME}"

if [ -z "$target" ]; then
  exit 0
fi

target="$(realpath "$target" 2> /dev/null || printf '%s' "$target")"
stop_at="$(realpath "$stop_at" 2> /dev/null || printf '%s' "$stop_at")"
home_rp="$(realpath "${HOME:-}" 2> /dev/null || printf '%s' "${HOME:-}")"

case "$target" in
  "" | "/") exit 0 ;;
esac

# Refuse to remove $HOME itself, anything above it, or anything that isn't
# strictly inside $HOME. Plain-dir entries are sourced from zoxide, which
# contains paths like `/`, `/opt/homebrew/...`, `/Library/Video`, etc.
# Without this check, alt-x on such a row in the picker would trigger
# `rm -rf` on a system path.
if [ -z "$home_rp" ] || [ "$target" = "$home_rp" ]; then
  exit 0
fi
case "$target" in
  "$home_rp"/*) ;;
  *) exit 0 ;;
esac

if [ -n "${TMUX:-}" ] && command -v tmux > /dev/null 2>&1; then
  tmux display-message -d 6000 "pick_session: removing $target" 2> /dev/null || true
fi

if [ -n "${TMUX:-}" ] && command -v tmux > /dev/null 2>&1; then
  tmux list-sessions -F $'#{session_name}\t#{session_path}' 2> /dev/null \
    | while IFS=$'\t' read -r name path; do
      [ -z "$name" ] && continue
      [ -z "$path" ] && continue
      path="$(realpath "$path" 2> /dev/null || printf '%s' "$path")"
      if [ "$path" = "$target" ]; then
        tmux kill-session -t "$name" 2> /dev/null || true
      fi
    done
fi

if [ -d "$target" ]; then
  rm -rf "$target"
fi

dir_is_effectively_empty_ignoring_ds_store() {
  local dir="$1"
  [ -n "$dir" ] || return 1
  [ -d "$dir" ] || return 1
  rm -f "$dir/.DS_Store" 2> /dev/null || true
  local any
  any="$(find "$dir" -mindepth 1 -maxdepth 1 ! -name '.DS_Store' -print -quit 2> /dev/null || true)"
  [ -z "$any" ]
}

cur="$(dirname "$target")"
while [ "$cur" != "/" ] && [ "$cur" != "$stop_at" ]; do
  if ! dir_is_effectively_empty_ignoring_ds_store "$cur"; then
    break
  fi
  rmdir "$cur" 2> /dev/null || break
  cur="$(dirname "$cur")"
done

if [ -n "${TMUX:-}" ] && command -v tmux > /dev/null 2>&1; then
  tmux display-message -d 6000 "pick_session: removed $target" 2> /dev/null || true
fi
