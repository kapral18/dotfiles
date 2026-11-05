#!/usr/bin/env bash
# Snapshot fzf's transient `{+f}` selection file (via
# `snapshot_fzf_selection.sh`) and dispatch the consumer in the background.
#
# Why this exists: fzf's `{+f}` placeholder produces a temp file that is
# unlinked after the bound action returns. Background consumers
# typically start after the action returns, so they race
# with fzf's cleanup and frequently see a missing or truncated file. Using
# the shared snapshot helper means every invocation gets a stable, unique
# path that the consumer owns.
#
# Optional `--filter-awk EXPR` strips rows during the snapshot (forwarded to
# `snapshot_fzf_selection.sh`). Used to drop header rows or similar
# decoration from the dispatched payload without coupling that policy into
# this dispatcher.
#
# Usage: dispatch_async.sh [--filter-awk EXPR] <consumer-cmd> <fzf-selection-file> [extra-args...]
set -euo pipefail

snap_cmd="$(cd "$(dirname "$0")" && pwd)/snapshot_fzf_selection.sh"

snap_args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --filter-awk)
      [ $# -ge 2 ] || exit 1
      snap_args+=("$1" "$2")
      shift 2
      ;;
    *) break ;;
  esac
done

consumer="${1:-}"
sel_in="${2:-}"
shift 2 || true

[ -n "$consumer" ] || exit 0
[ -n "$sel_in" ] && [ -f "$sel_in" ] || exit 0

snap="$("$snap_cmd" "${snap_args[@]+"${snap_args[@]}"}" "$sel_in")" || exit 0
[ -n "$snap" ] || exit 0

# The consumer keeps fzf's `--listen` env (FZF_SOCK, FZF_API_KEY) so it can
# post follow-up actions back to fzf.
"$HOME/lib/shared/detach.sh" "$consumer" "$snap" "$@" < /dev/null > /dev/null 2>&1 &
