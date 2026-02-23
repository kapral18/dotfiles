#!/usr/bin/env bash
set -euo pipefail

root="${1:-}"
shift || true

[ -n "$root" ] || exit 0
[ $# -gt 0 ] || exit 0

if ! command -v ,w >/dev/null 2>&1; then
  if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
    tmux display-message "tmux: missing command: ,w" 2>/dev/null || true
  fi
  exit 0
fi

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
pending_file="${cache_dir}/pick_session_pending.tsv"

cd "$root"

,w remove --tmux-notify --paths "$@"

# Cleanup pending entries that are actually gone.
if [ -f "$pending_file" ]; then
  tmp="$(mktemp -t pick_session_pending.XXXXXX)"
  cp "$pending_file" "$tmp"
  p=""
  for p in "$@"; do
    if [ ! -d "$p" ]; then
      grep -v -F $'WT\t'"$p" "$tmp" >"${tmp}.2" || true
      mv -f "${tmp}.2" "$tmp"
    fi
  done
  mv -f "$tmp" "$pending_file"
fi

# Opportunistically refresh the cache after removals finish.
if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux run-shell -b "$HOME/.config/tmux/scripts/pick_session_index_update.sh --force --quiet" 2>/dev/null || true
fi
