#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/../bash_utils_lib.sh"
source "$(dirname "$0")/../worktree_lib.sh"

show_usage() {
  cat <<EOF
Usage: ,w mv [-q|--quiet] [--focus] [--keep-path] [--path <new_path>] <from> <to>

Move/rename a worktree as a unit (git worktree + tmux + zoxide).

Arguments:
  <from>             Worktree branch name or worktree path
  <to>               New branch name

Options:
  -q, --quiet        Suppress informational output
  --path <new_path>  Override the destination worktree path
  --keep-path        Do not move the directory (branch rename only)
  --focus            Switch/attach to the resulting tmux session
  -h, --help         Show this help message
EOF
}

quiet_mode=0
focus_mode=0
keep_path=0
new_path=""

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
  --focus)
    focus_mode=1
    shift
    ;;
  --keep-path)
    keep_path=1
    shift
    ;;
  --path)
    if [ $# -lt 2 ]; then
      show_usage
      exit 1
    fi
    new_path="$2"
    shift 2
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

if [ $# -ne 2 ]; then
  show_usage
  exit 1
fi

from="$1"
to_branch="$2"

parent_dir=$(_get_worktree_parent_dir)
parent_name=$(basename "$parent_dir")

_comma_w_prune_stale_worktrees "$quiet_mode"

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
      echo "Worktree '$needle_path' is not on a local branch ($branch_ref)." >&2
      return 1
    fi
  done < <(git worktree list --porcelain)

  return 1
}

from_branch=""
from_path=""
old_path=""

if [ -e "$from" ]; then
  from_path="$from"
  from_branch="$(find_branch_for_worktree_path "$from_path" || true)"
  if [ -z "$from_branch" ]; then
    echo "Failed to resolve worktree branch for path: $from_path" >&2
    exit 1
  fi
else
  from_branch="$from"
  from_path="$(_comma_w_find_worktree_path_for_branch "$from_branch" || true)"
  if [ -z "$from_path" ]; then
    echo "Failed to resolve worktree path for branch: $from_branch" >&2
    exit 1
  fi
fi

old_path="$from_path"

if [ -z "$new_path" ]; then
  new_path="$parent_dir/$to_branch"
fi

old_session="$(_comma_w_tmux_session_name "$parent_name" "$from_branch")"
_remove_worktree_tmux_session "$quiet_mode" "$from_path" "$old_session"

if [ "$from_branch" != "$to_branch" ]; then
  if git show-ref --verify --quiet "refs/heads/$to_branch"; then
    echo "Branch '$to_branch' already exists locally." >&2
    exit 1
  fi
  if _comma_w_find_worktree_path_for_branch "$to_branch" >/dev/null 2>&1; then
    echo "A worktree already exists for branch '$to_branch'." >&2
    exit 1
  fi
fi

if [ "$keep_path" -eq 0 ] && [ "$from_path" != "$new_path" ]; then
  mkdir -p "$(dirname "$new_path")"
  git worktree move "$from_path" "$new_path"
  from_path="$new_path"
fi

if [ "$from_branch" != "$to_branch" ]; then
  if ! git branch -m "$from_branch" "$to_branch" 2>/dev/null; then
    git -C "$from_path" branch -m "$from_branch" "$to_branch"
  fi
fi

new_session="$(_comma_w_tmux_session_name "$parent_name" "$to_branch")"
_add_worktree_tmux_session "$quiet_mode" "$parent_name" "$to_branch" "$from_path"

if command -v zoxide &>/dev/null; then
  if [ "$old_path" != "$from_path" ]; then
    zoxide remove "$old_path" 2>/dev/null || true
  fi
  zoxide add "$from_path" 2>/dev/null || true
fi

if [ "$focus_mode" -eq 1 ]; then
  _comma_w_focus_tmux_session "$quiet_mode" "$new_session" "$from_path" || true
fi

if [ "$quiet_mode" -eq 0 ]; then
  printf '%s\t%s\n' "$to_branch" "$from_path"
fi
