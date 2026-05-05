#!/usr/bin/env bash
# Stage GH-picker selection so the popup loop can hand off to a ,ralph go run.
# Usage: handoff_to_ralph_pin.sh KIND REPO NUM URL PIN_FILE
set -euo pipefail

kind="${1:-}"
repo="${2:-}"
num="${3:-}"
url="${4:-}"
out_file="${5:-}"

[ -n "$out_file" ] || exit 0
[ -n "$kind" ] && [ -n "$repo" ] && [ -n "$num" ] || exit 0

title=""
if command -v gh > /dev/null 2>&1; then
  case "$kind" in
    pr)
      title="$(gh pr view "$num" --repo "$repo" --json title -q .title 2> /dev/null || true)"
      ;;
    issue)
      title="$(gh issue view "$num" --repo "$repo" --json title -q .title 2> /dev/null || true)"
      ;;
  esac
fi

worktree=""
if command -v git > /dev/null 2>&1 && git rev-parse --show-toplevel > /dev/null 2>&1; then
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

printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$kind" "$repo" "$num" "$url" "$title" "$worktree" > "$out_file"
