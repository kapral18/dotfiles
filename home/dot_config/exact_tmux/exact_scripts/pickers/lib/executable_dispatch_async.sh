#!/usr/bin/env bash
# Snapshot fzf's transient `{+f}` selection file (via
# `snapshot_fzf_selection.sh`) and dispatch the consumer in the tmux
# background.
#
# Why this exists: fzf's `{+f}` placeholder produces a temp file that is
# unlinked after the bound action returns. Background consumers launched via
# `tmux run-shell -b` typically start after the action returns, so they race
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

extra=""
for a in "$@"; do
  extra+=" $(printf %q "$a")"
done

# Propagate fzf's `--listen` env vars to the background consumer. fzf sets its
# vars on every child process it spawns (execute, execute-silent, transform, ...).
# `tmux run-shell -b`, however, uses the tmux server's env and would drop them,
# so we inline the assignments into the command string. The consumer can then
# post follow-up actions back to fzf.
fzf_env_prefix=""
append_env_prefix() {
  local name="$1"
  local value="${!name:-}"
  [ -n "$value" ] || return 0
  fzf_env_prefix+="${name}=$(printf %q "$value") "
}

append_env_prefix FZF_SOCK
append_env_prefix FZF_PORT
append_env_prefix FZF_API_KEY

if command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux run-shell -b "${fzf_env_prefix}$(printf %q "$consumer") $(printf %q "$snap")${extra}" 2> /dev/null || true
else
  nohup "$consumer" "$snap" "$@" < /dev/null > /dev/null 2>&1 &
fi
