#!/usr/bin/env bash
# Consume a Ralph handoff pin and prompt for a goal, then spawn a ,ralph go run.
# Usage: handoff_to_ralph_apply.sh PIN_FILE
set -euo pipefail

pin_file="${1:-}"
[ -n "$pin_file" ] || exit 0
[ -f "$pin_file" ] || exit 0

script_dir="$(cd "$(dirname "$0")" && pwd)"
handoff_namespace="$script_dir/handoff_namespace.py"

IFS=$'\t' read -r kind repo num url title worktree context_file seed count < "$pin_file"
rm -f "$pin_file" 2> /dev/null || true

[ -n "$kind" ] && [ -n "$repo" ] && [ -n "$num" ] || exit 0

label="${title:-$kind #$num}"
seed="${seed:-$kind $repo#$num: $label}"
# The Ralph context sibling lives inside the handoff namespace, which gh_popup
# ends as soon as this hand-off is queued. Retain a lifecycle-managed 0600 copy
# under the handoff root BEFORE queuing the asynchronous command-prompt and seed
# that copy, so the deferred `,ralph go` run can still read it. Fail closed
# (no prompt) rather than queue a broken context reference.
if [ -n "${context_file:-}" ] && [ -f "$context_file" ]; then
  retained_context="$("$handoff_namespace" retain-context "$context_file")" || exit 0
  [ -n "$retained_context" ] || exit 0
  seed="$seed | Use GitHub dashboard context: $retained_context"
fi
ws_arg="$(printf %q "$worktree")"

tmux command-prompt \
  -I "$seed" \
  -p "ralph go goal:" \
  "run-shell -b \",ralph go --workspace $ws_arg --goal \\\"%1\\\"\""
