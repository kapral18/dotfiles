#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/../bash_utils_lib.sh"
source "$(dirname "$0")/../worktree_lib.sh"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required dependency: '$cmd'." >&2
    exit 1
  fi
}

show_usage() {
  cat <<EOF
Usage: ,w switch [-q|--quiet] [query...]

Interactively pick a worktree and switch/attach to its tmux session.

Options:
  -q, --quiet       Suppress informational output
  -h, --help        Show this help message
EOF
}

quiet_mode=0

while [ $# -gt 0 ]; do
  case "$1" in
  -h | --help)
    show_usage
    exit 0
    ;;
  -q | --quiet)
    quiet_mode=1
    shift
    ;;
  --)
    shift
    break
    ;;
  -*)
    show_usage
    exit 1
    ;;
  *)
    break
    ;;
  esac
done

require_cmd fzf

parent_dir=$(_get_worktree_parent_dir)
parent_name=$(basename "$parent_dir")

query="$*"

mapfile -t candidates < <("$(dirname "$0")/wt_ls.sh" --selectable)
if [ ${#candidates[@]} -eq 0 ]; then
  echo "No selectable worktrees found."
  exit 1
fi

selected="$(
  printf '%s\n' "${candidates[@]}" | fzf --no-preview --query "$query" --prompt "worktree> "
)"

if [ -z "$selected" ]; then
  echo "No worktree selected."
  exit 1
fi

IFS=$'\t' read -r branch worktree_path <<<"$selected"
if [ -z "$branch" ] || [ -z "$worktree_path" ]; then
  echo "Invalid selection." >&2
  exit 1
fi

_add_worktree_tmux_session "$quiet_mode" "$parent_name" "$branch" "$worktree_path"

session_name="$(_comma_w_tmux_session_name "$parent_name" "$branch")"
if ! _comma_w_focus_tmux_session "$quiet_mode" "$session_name" "$worktree_path"; then
  if [ "$quiet_mode" -eq 0 ]; then
    echo "$worktree_path"
  fi
fi
