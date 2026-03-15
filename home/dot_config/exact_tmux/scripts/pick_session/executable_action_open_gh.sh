#!/usr/bin/env bash
set -euo pipefail

# Opens a GitHub PR or issue URL extracted from a pick_session TSV line.
# Fast path: uses the cached URL from the meta field.
# Fallback: delegates to ,gh-prw / ,gh-issuew which have sophisticated
# resolution logic (commit SHA, upstream owner, PR body parsing, etc.)
#
# Usage: action_open_gh.sh <pr|issue> <fzf-temp-file>

mode="${1:-}"
shift || true
file="${1:-}"

if [ -z "$mode" ] || [ -z "$file" ] || [ ! -f "$file" ]; then
  exit 0
fi

line="$(head -n 1 "$file" 2> /dev/null || true)"
[ -n "$line" ] || exit 0

meta="$(printf '%s' "$line" | awk -F $'\t' '{print $4}')"
path="$(printf '%s' "$line" | awk -F $'\t' '{print $3}')"

url=""
if [ -n "$meta" ]; then
  IFS='|' read -ra parts <<< "$meta"
  for part in "${parts[@]}"; do
    case "$mode" in
      pr)
        case "$part" in
          pr=*)
            val="${part#pr=}"
            url="${val#*:}"
            url="${url#*:}"
            ;;
        esac
        ;;
      issue)
        case "$part" in
          issue=*)
            val="${part#issue=}"
            url="${val#*:}"
            url="${url#*:}"
            ;;
        esac
        ;;
    esac
  done
fi

if [ -n "$url" ]; then
  open "$url" 2> /dev/null || xdg-open "$url" 2> /dev/null || true
  exit 0
fi

if [ -n "$path" ] && [ -d "$path" ]; then
  case "$mode" in
    pr)
      if command -v ,gh-prw > /dev/null 2>&1; then
        (cd "$path" && ,gh-prw 2> /dev/null) \
          || tmux display-message "No PR found for this entry" 2> /dev/null || true
      else
        tmux display-message "No PR found for this entry" 2> /dev/null || true
      fi
      ;;
    issue)
      if command -v ,gh-issuew > /dev/null 2>&1; then
        (cd "$path" && ,gh-issuew 2> /dev/null) \
          || tmux display-message "No issue found for this entry" 2> /dev/null || true
      else
        tmux display-message "No issue found for this entry" 2> /dev/null || true
      fi
      ;;
  esac
else
  tmux display-message "No ${mode} found for this entry" 2> /dev/null || true
fi
