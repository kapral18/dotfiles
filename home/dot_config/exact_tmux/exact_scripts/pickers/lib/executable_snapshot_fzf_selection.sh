#!/usr/bin/env bash
# Snapshot fzf's transient `{+f}` selection file to a stable per-binding
# mktemp under `$XDG_CACHE_HOME/tmux`. Prints the snapshot path on stdout.
#
# Why this exists: fzf's `{+f}` placeholder produces a temp file that is
# unlinked after the bound action returns. Anything that consumes the
# selection asynchronously (via `tmux run-shell -b`) or after a follow-up
# fzf action races with that cleanup. Snapshotting to a unique mktemp gives
# the consumer a stable path it owns the lifecycle of.
#
# Each invocation mints its own unique path (mktemp `XXXXXX` template), so
# rapid keypresses and concurrent pickers cannot clobber each other's
# snapshots.
#
# Optional `--filter-awk EXPR` strips rows during the snapshot (used by the
# GH picker to drop `header` rows; the session picker has no header rows
# and passes no filter).
#
# Consumers are responsible for unlinking the snapshot when they finish
# reading it.
#
# Usage: snapshot_fzf_selection.sh [--filter-awk EXPR] <sel_in>
set -euo pipefail

filter_awk=""
while [ $# -gt 0 ]; do
  case "$1" in
    --filter-awk)
      [ $# -ge 2 ] || exit 1
      filter_awk="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *) break ;;
  esac
done

sel_in="${1:-}"
[ -n "$sel_in" ] && [ -f "$sel_in" ] || exit 1

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
mkdir -p "$cache_dir" 2> /dev/null || true
snap="$(mktemp "${cache_dir}/picker_snap.XXXXXX")"

if [ -n "$filter_awk" ]; then
  awk -F $'\t' "$filter_awk" "$sel_in" > "$snap" 2> /dev/null || true
else
  cp "$sel_in" "$snap" 2> /dev/null || true
fi

printf '%s\n' "$snap"
