#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/../worktree_lib.sh"

show_usage() {
  cat <<EOF
Usage: f-wtree remove

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
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)
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

mapfile -t worktrees < <(git worktree list -v | fzf --no-preview --ansi --multi)

if [ ${#worktrees[@]} -eq 0 ]; then
  echo "No worktrees selected."
  exit 1
fi

default_branch=$(git config --get init.defaultbranch || echo "main")
remotes_to_check=()

for worktree in "${worktrees[@]}"; do
  worktree_path=$(echo "$worktree" | awk '{print $1}')
  worktree_branch=$(echo "$worktree" | awk '{
        last = $NF
        gsub(/^[[(]|[])]$/, "", last)
        print last
    }')

  if [ "$worktree_branch" = "HEAD" ]; then
    echo "Skipping worktree at '$worktree_path'. It's in detached HEAD state."
    continue
  fi

  if [ "$worktree_branch" = "$default_branch" ]; then
    echo "Skipping default branch at '$worktree_path'"
    continue
  fi

  echo "Removing worktree: $worktree_path ($worktree_branch)"
  git worktree remove "$worktree_path"

  remote_branch=$(git rev-parse --abbrev-ref "$worktree_branch"@{upstream} 2>/dev/null || true)
  if [ -n "$remote_branch" ]; then
    remote=$(echo "$remote_branch" | cut -d'/' -f1)
    if [ -n "$remote" ] && [ "$remote" != "origin" ] && [ "$remote" != "upstream" ]; then
      remotes_to_check+=("$remote")
    fi
  fi

  if git worktree list --porcelain | grep branch | grep -qw "$worktree_branch"; then
    echo "Branch '$worktree_branch' is still used by other worktrees, skipping deletion."
  else
    git branch -D "$worktree_branch"
  fi

  _remove_worktree_tmux_session "$worktree_path"

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
  for remote in $(printf '%s\n' "${remotes_to_check[@]}" | sort -u); do
    if ! git worktree list -v | grep -q "\b$remote\b"; then
      echo "Removing unused remote: $remote"
      git remote remove "$remote"
    fi
  done
fi
