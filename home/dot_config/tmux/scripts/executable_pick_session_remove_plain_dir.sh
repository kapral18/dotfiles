#!/usr/bin/env bash
set -euo pipefail

target="${1:-}"
stop_at="${2:-$HOME}"

if [ -z "$target" ]; then
  exit 0
fi

target="$(realpath "$target" 2>/dev/null || printf '%s' "$target")"
stop_at="$(realpath "$stop_at" 2>/dev/null || printf '%s' "$stop_at")"

case "$target" in
  ""|"/") exit 0 ;;
esac

if [ "$target" = "$HOME" ]; then
  exit 0
fi

if [ -n "${TMUX:-}" ] && command -v tmux >/dev/null 2>&1; then
  tmux display-message -d 6000 "pick_session: removing $target" 2>/dev/null || true
fi

if [ -n "${TMUX:-}" ] && command -v tmux >/dev/null 2>&1; then
  tmux list-sessions -F $'#{session_name}\t#{session_path}' 2>/dev/null |
    while IFS=$'\t' read -r name path; do
      [ -z "$name" ] && continue
      [ -z "$path" ] && continue
      path="$(realpath "$path" 2>/dev/null || printf '%s' "$path")"
      if [ "$path" = "$target" ]; then
        tmux kill-session -t "$name" 2>/dev/null || true
      fi
    done
fi

if [ -d "$target" ]; then
  rm -rf "$target"
fi

cur="$(dirname "$target")"
while [ "$cur" != "/" ] && [ "$cur" != "$stop_at" ]; do
  if [ -n "$(ls -A "$cur" 2>/dev/null)" ]; then
    break
  fi
  rmdir "$cur" 2>/dev/null || break
  cur="$(dirname "$cur")"
done

if [ -n "${TMUX:-}" ] && command -v tmux >/dev/null 2>&1; then
  tmux display-message -d 6000 "pick_session: removed $target" 2>/dev/null || true
fi
