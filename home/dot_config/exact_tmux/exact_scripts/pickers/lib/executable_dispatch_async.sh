#!/usr/bin/env bash
# Snapshot fzf's transient {+f} selection file to a stable cache path, then
# dispatch the consumer in the tmux background.
#
# Why this exists: fzf's `{+f}` placeholder produces a temp file that is unlinked
# after the bound action returns. Background consumers launched via
# `tmux run-shell -b` typically start after the action returns, so they race
# with fzf's cleanup and frequently see a missing or truncated file. Earlier
# this picker captured selections into a single shared cache file
# (`pick_session_fzf_selected.tsv` etc), which decoupled the lifecycle but
# introduced a clobber race when two pickers / two rapid keypresses fought
# over the same path.
#
# This helper takes the per-binding `{+f}` file, copies it to a unique
# `mktemp` cache path, and hands that stable path to the consumer. Consumers
# are responsible for unlinking the snapshot when they finish reading it.
#
# Usage: dispatch_async.sh <consumer-cmd> <fzf-selection-file> [extra-args...]
set -euo pipefail

consumer="${1:-}"
sel_in="${2:-}"
shift 2 || true

[ -n "$consumer" ] || exit 0
[ -n "$sel_in" ] && [ -f "$sel_in" ] || exit 0

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
mkdir -p "$cache_dir" 2> /dev/null || true
snap="$(mktemp "${cache_dir}/picker_async_sel.XXXXXX")"
cp "$sel_in" "$snap" 2> /dev/null || true

extra=""
for a in "$@"; do
  extra+=" $(printf %q "$a")"
done

if command -v tmux > /dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  tmux run-shell -b "$(printf %q "$consumer") $(printf %q "$snap")${extra}" 2> /dev/null || true
else
  nohup "$consumer" "$snap" "$@" < /dev/null > /dev/null 2>&1 &
fi
