#!/usr/bin/env bash
# Stage GH-picker selection so the popup loop can hand off to a ,ralph go run.
# Usage: handoff_to_ralph_pin.sh SELECTION_FILE PIN_FILE
set -euo pipefail

selection_file="${1:-}"
out_file="${2:-}"

[ -n "$out_file" ] || exit 0
[ -n "$selection_file" ] && [ -f "$selection_file" ] || exit 0

repo="$(awk -F $'\t' '$2 != "header" && $3 != "" { print $3; exit }' "$selection_file" 2> /dev/null || true)"

worktree=""
if [ -n "$repo" ] && command -v git > /dev/null 2>&1 && git rev-parse --show-toplevel > /dev/null 2>&1; then
  worktree="$(git -C "$(git rev-parse --show-toplevel)" worktree list --porcelain 2> /dev/null \
    | awk -v want="${repo##*/}" '
        /^worktree / { path = substr($0, 10) }
        /^branch / {
          br = substr($0, 8)
          gsub(/^refs\/heads\//, "", br)
          if (br ~ ("/?(pr-?)" want "?[0-9]*$") || br ~ ("/?(pr|issue)/?(" want "?)?[0-9]+$")) {
            print path; exit
          }
        }
      ' | head -n 1)"
fi
[ -z "$worktree" ] && worktree="$(pwd)"

script_dir="$(cd "$(dirname "$0")" && pwd)"
context_builder="$script_dir/../github/lib/gh_ralph_handoff_context.py"

python3 "$context_builder" "$selection_file" "$out_file" --workspace "$worktree" 2> /dev/null || true
