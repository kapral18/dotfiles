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

list_worktrees_porcelain() {
  local line key value
  local worktree_path=""
  local branch_ref=""
  local detached=0
  local locked=0

  while IFS= read -r line; do
    key="${line%% *}"
    value="${line#* }"

    case "$key" in
    worktree)
      if [ -n "$worktree_path" ]; then
        printf '%s\t%s\t%s\t%s\n' "$worktree_path" "$branch_ref" "$detached" "$locked"
      fi
      worktree_path="$value"
      branch_ref=""
      detached=0
      locked=0
      ;;
    branch)
      branch_ref="$value"
      ;;
    detached)
      detached=1
      ;;
    locked)
      locked=1
      ;;
    esac
  done < <(git worktree list --porcelain)

  if [ -n "$worktree_path" ]; then
    printf '%s\t%s\t%s\t%s\n' "$worktree_path" "$branch_ref" "$detached" "$locked"
  fi
}

worktree_branch_in_use() {
  local branch="$1"
  local target="branch refs/heads/${branch}"
  local line

  while IFS= read -r line; do
    case "$line" in
    "$target") return 0 ;;
    esac
  done < <(git worktree list --porcelain)

  return 1
}

show_usage() {
  cat <<EOF
Usage: ,w remove

Interactively remove git worktrees.

Options:
  -h, --help        Show this help message

Description:
  Opens an interactive fzf selector to choose worktrees to remove.
  For each selected worktree:
  - Removes the worktree directory
  - Deletes the associated local branch
  - Removes unused fork remotes
  - Cleans up empty parent directories
  - Removes path from zoxide database
  - Kills associated tmux session

Notes:
  - The default branch (main/master) cannot be removed
  - Worktrees in detached HEAD state will be skipped
  - Set COMMA_W_PRUNE=0 to disable automatic $(git worktree prune)
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

require_cmd fzf

_comma_w_prune_stale_worktrees 0

default_branch=$(git config --get init.defaultbranch || echo "main")

parent_dir=$(_get_worktree_parent_dir)
parent_name=$(basename "$parent_dir")

mapfile -t selectable_worktrees < <(
  list_worktrees_porcelain | awk -F'\t' -v default_branch="$default_branch" '
    {
      path=$1
      branch_ref=$2
      detached=$3
      locked=$4

      if (detached == 1) next
      if (locked == 1) next
      if (branch_ref !~ "^refs/heads/") next
      branch=branch_ref
      sub("^refs/heads/", "", branch)

      if (branch == default_branch) next

      printf "%s\t%s\n", path, branch
    }
  '
)

if [ ${#selectable_worktrees[@]} -eq 0 ]; then
  echo "No removable worktrees found."
  exit 1
fi

mapfile -t worktrees < <(printf '%s\n' "${selectable_worktrees[@]}" | fzf --no-preview --multi)

if [ ${#worktrees[@]} -eq 0 ]; then
  echo "No worktrees selected."
  exit 1
fi

remotes_to_check=()

_get_branch_upstream_remote() {
  local branch="$1"
  local remote

  remote="$(git for-each-ref --format='%(upstream:remotename)' "refs/heads/$branch" 2>/dev/null || true)"
  case "$remote" in
  "" | .) echo "" ;;
  *) echo "$remote" ;;
  esac
}

_infer_remote_from_prefixed_branch() {
  local branch="$1"
  local candidate

  case "$branch" in
  *__*)
    candidate="${branch%%__*}"
    if git remote get-url "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
    else
      echo ""
    fi
    ;;
  *)
    echo ""
    ;;
  esac
}

for worktree in "${worktrees[@]}"; do
  IFS=$'\t' read -r worktree_path worktree_branch _ <<<"$worktree"

  echo "Removing worktree: $worktree_path ($worktree_branch)"
  if ! git worktree remove "$worktree_path"; then
    echo "Failed to remove worktree: $worktree_path" >&2
    continue
  fi

  remote="$(_get_branch_upstream_remote "$worktree_branch")"
  if [ -z "$remote" ]; then
    remote="$(_infer_remote_from_prefixed_branch "$worktree_branch")"
  fi
  if [ -n "$remote" ] && [ "$remote" != "origin" ] && [ "$remote" != "upstream" ]; then
    remotes_to_check+=("$remote")
  fi

  if worktree_branch_in_use "$worktree_branch"; then
    echo "Branch '$worktree_branch' is still used by other worktrees, skipping deletion."
  else
    git branch -D "$worktree_branch"
  fi

  _remove_worktree_tmux_session 0 "$worktree_path" "$(_comma_w_tmux_session_name "$parent_name" "$worktree_branch")"

  current_dir=$(dirname "$worktree_path")
  while [ -z "$(ls -A "$current_dir" 2>/dev/null)" ]; do
    parent_dir=$(dirname "$current_dir")
    rmdir "$current_dir"
    current_dir="$parent_dir"
  done

  if command -v zoxide &>/dev/null; then
    zoxide remove "$worktree_path"
  fi
done

if [ ${#remotes_to_check[@]} -gt 0 ]; then
  _remote_exists() {
    local remote="$1"
    git remote get-url "$remote" >/dev/null 2>&1
  }

  _remote_has_any_local_tracking_branch() {
    local remote="$1"
    local upstream_remote

    while IFS= read -r upstream_remote; do
      case "$upstream_remote" in
      "$remote") return 0 ;;
      esac
    done < <(git for-each-ref --format='%(upstream:remotename)' refs/heads)

    return 1
  }

  _remote_has_any_local_prefixed_branch() {
    local remote="$1"
    local branch

    while IFS= read -r branch; do
      case "$branch" in
      "${remote}"__*) return 0 ;;
      esac
    done < <(git for-each-ref --format='%(refname:short)' refs/heads)

    return 1
  }

  for remote in $(printf '%s\n' "${remotes_to_check[@]}" | sort -u); do
    case "$remote" in
    "" | origin | upstream | .)
      continue
      ;;
    esac

    if ! _remote_exists "$remote"; then
      echo "Skipping remote '$remote' (not found)."
      continue
    fi

    if _remote_has_any_local_tracking_branch "$remote"; then
      echo "Keeping remote '$remote' (still tracked by local branches)."
      continue
    fi

    if _remote_has_any_local_prefixed_branch "$remote"; then
      echo "Keeping remote '$remote' (still referenced by local '${remote}__*' branches)."
      continue
    fi

    echo "Removing unused remote: $remote"
    git remote remove "$remote"
  done
fi
