#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/../bash_utils_lib.sh"

show_usage() {
  cat <<EOF
Usage: ,w doctor

Check ,w dependencies and repository state.

Options:
  -h, --help        Show this help message
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
  -h | --help)
    show_usage
    exit 0
    ;;
  *)
    echo "Error: Unknown option '$1'" >&2
    show_usage
    exit 1
    ;;
  esac
done

missing=0

check_cmd() {
  local cmd="$1"
  local label="${2:-$cmd}"
  if command -v "$cmd" >/dev/null 2>&1; then
    printf 'ok   %s\n' "$label"
  else
    printf 'miss %s\n' "$label"
    missing=1
  fi
}

check_cmd git
check_cmd fzf
check_cmd gh
check_cmd tmux
check_cmd zoxide
check_cmd bat

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: not inside a git work tree." >&2
  exit 1
fi

parent_dir=$(_get_worktree_parent_dir)
parent_name=$(basename "$parent_dir")

stale_paths=()
worktree_path=""
line=""

while IFS= read -r line; do
  case "$line" in
  worktree\ *)
    worktree_path="${line#worktree }"
    if [ -n "$worktree_path" ] && [ ! -e "$worktree_path" ]; then
      stale_paths+=("$worktree_path")
    fi
    ;;
  esac
done < <(git worktree list --porcelain 2>/dev/null || true)

if [ ${#stale_paths[@]} -gt 0 ]; then
  echo
  echo "Stale worktree paths (missing on disk):"
  printf '  %s\n' "${stale_paths[@]}"
  echo "Run: ,w prune"
fi

if [ -n "${TMUX:-}" ] && ! command -v tmux >/dev/null 2>&1; then
  echo
  echo "Warning: TMUX is set but 'tmux' is missing."
fi

if command -v tmux >/dev/null 2>&1; then
  stale_sessions=()
  session_has_any_existing_pane_path() {
    local session_name="$1"
    local pane_path

    while IFS= read -r pane_path; do
      [ -z "$pane_path" ] && continue
      if [ -e "$pane_path" ]; then
        return 0
      fi
    done < <(tmux list-panes -t "$session_name" -F '#{pane_current_path}' 2>/dev/null || true)

    return 1
  }

  while IFS=$'\t' read -r session_name _; do
    [ -z "$session_name" ] && continue
    case "$session_name" in
    "${parent_name}"\|*) ;;
    *)
      continue
      ;;
    esac

    if ! session_has_any_existing_pane_path "$session_name"; then
      stale_sessions+=("$session_name")
    fi
  done < <(tmux list-sessions -F $'#{session_name}\t#{session_path}' 2>/dev/null || true)

  if [ ${#stale_sessions[@]} -gt 0 ]; then
    echo
    echo "Stale ,w tmux sessions for '$parent_name' (no existing pane paths):"
    printf '  %s\n' "${stale_sessions[@]}"
    echo "Run: ,w prune --apply"
  fi
fi

exit "$missing"
