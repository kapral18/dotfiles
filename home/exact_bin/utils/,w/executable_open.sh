#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/../bash_utils_lib.sh"
source "$(dirname "$0")/../worktree_lib.sh"

show_usage() {
  cat <<EOF
Usage: ,w open [-q|--quiet] <branch|path>

Focus a worktree by switching/attaching to its tmux session.

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

if [ $# -ne 1 ]; then
  show_usage
  exit 1
fi

target="$1"

parent_dir=$(_get_worktree_parent_dir)
parent_name=$(basename "$parent_dir")

find_branch_for_worktree_path() {
  local needle_path="$1"
  needle_path="$(realpath "$needle_path" 2>/dev/null || printf '%s' "$needle_path")"
  local line key value
  local worktree_path=""
  local branch_ref=""
  local worktree_realpath=""

  while IFS= read -r line; do
    key="${line%% *}"
    value="${line#* }"

    case "$key" in
    worktree)
      worktree_path="$value"
      branch_ref=""
      worktree_realpath="$(realpath "$worktree_path" 2>/dev/null || printf '%s' "$worktree_path")"
      ;;
    branch)
      branch_ref="$value"
      ;;
    esac

    if [ -n "$worktree_path" ] && [ "$worktree_realpath" = "$needle_path" ] && [ -n "$branch_ref" ]; then
      if [[ "$branch_ref" == refs/heads/* ]]; then
        printf '%s\n' "${branch_ref#refs/heads/}"
        return 0
      fi
      return 1
    fi
  done < <(git worktree list --porcelain)

  return 1
}

branch=""
worktree_path=""

if [ -e "$target" ]; then
  worktree_path="$target"
  branch="$(find_branch_for_worktree_path "$worktree_path" || true)"
  if [ -z "$branch" ]; then
    echo "Failed to determine branch for worktree path: $worktree_path" >&2
    exit 1
  fi
else
  branch="$target"
  worktree_path="$(_comma_w_find_worktree_path_for_branch "$branch" || true)"
  if [ -z "$worktree_path" ]; then
    echo "Failed to determine worktree path for branch: $branch" >&2
    exit 1
  fi
fi

_add_worktree_tmux_session "$quiet_mode" "$parent_name" "$branch" "$worktree_path"
session_name="$(_comma_w_tmux_session_name "$parent_name" "$branch")"

if ! _comma_w_focus_tmux_session "$quiet_mode" "$session_name" "$worktree_path"; then
  if [ "$quiet_mode" -eq 0 ]; then
    echo "$worktree_path"
  fi
fi
