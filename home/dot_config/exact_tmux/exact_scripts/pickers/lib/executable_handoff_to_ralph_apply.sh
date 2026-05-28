#!/usr/bin/env bash
# Consume a Ralph handoff pin and prompt for a goal, then spawn a ,ralph go run.
# Usage: handoff_to_ralph_apply.sh PIN_FILE
set -euo pipefail

pin_file="${1:-}"
[ -n "$pin_file" ] || exit 0
[ -f "$pin_file" ] || exit 0

IFS=$'\t' read -r kind repo num url title worktree context_file seed count < "$pin_file"
rm -f "$pin_file" 2> /dev/null || true

[ -n "$kind" ] && [ -n "$repo" ] && [ -n "$num" ] || exit 0

label="${title:-$kind #$num}"
seed="${seed:-$kind $repo#$num: $label}"
if [ -n "${context_file:-}" ] && [ -f "$context_file" ]; then
  seed="$seed | Use GitHub dashboard context: $context_file"
fi
ws_arg="$(printf %q "$worktree")"

tmux command-prompt \
  -I "$seed" \
  -p "ralph go goal:" \
  "run-shell -b \",ralph go --workspace $ws_arg --goal \\\"%1\\\"\""
