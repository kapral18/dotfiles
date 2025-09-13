#!/usr/bin/env bash
# Shared utility functions for bash scripts

# Safe command execution with error handling
_safe_exec_cmd() {
  local output
  if output=$("$@" 2>&1); then
    echo "$output"
    return 0
  else
    echo "Error executing command: $*" >&2
    echo "Output: $output" >&2
    return 1
  fi
}

# Check GitHub API rate limit
_check_rate_limit() {
  local remaining
  if ! remaining=$(_safe_exec_cmd gh api rate_limit --jq '.rate.remaining'); then
    return 1
  fi

  if [ "$remaining" -lt 100 ]; then
    echo "Warning: GitHub API rate limit is low ($remaining remaining)" >&2
    return 1
  fi
  return 0
}

# Check if auto-merge is enabled for a PR
_is_auto_merge_enabled() {
  local pr_number="$1"
  local auto_merge_enabled
  if ! auto_merge_enabled=$(_safe_exec_cmd gh pr view "$pr_number" --json autoMergeRequest --jq '.autoMergeRequest != null'); then
    return 1
  fi
  [ "$auto_merge_enabled" = "true" ]
}

# Check if PR has the specific comment
is_pr_commented() {
  local pr_number="$1"
  local comment_body
  if ! comment_body=$(_safe_exec_cmd gh pr view "$pr_number" --json comments --jq '.comments[].body'); then
    return 1
  fi
  echo "$comment_body" | grep -q "Please do not merge this pull request"
}

# Process a single PR for auto-merge disabling
_process_single_pr() {
  local pr_number="$1"
  local actions_performed=false

  if ! is_pr_commented "$pr_number"; then
    echo "PR #$pr_number: Adding comment"
    if ! _safe_exec_cmd gh pr comment "$pr_number" --body "We have disabled auto-merge for this PR. Please do not merge this pull request. We will re-enable auto-merge once the PR is ready for merging."; then
      return 1
    fi
    actions_performed=true
  fi

  if _is_auto_merge_enabled "$pr_number"; then
    echo "PR #$pr_number: Disabling auto-merge"
    if ! _safe_exec_cmd gh pr merge "$pr_number" --disable-auto; then
      return 1
    fi
    actions_performed=true
  fi

  if [ "$actions_performed" = true ]; then
    echo "Processed PR #$pr_number"
  else
    echo "Skipping PR #$pr_number: Already fully processed"
  fi
  return 0
}

# Get split branch name (remote and branch)
_get_split_branch_name() {
  if [ $# -eq 0 ]; then
    echo "Error: _get_split_branch_name requires a branch name argument" >&2
    return 1
  fi
  echo "$1" | awk -F'/' '{print $1; $1=""; gsub(/^\//, ""); print}'
}

# Confirmation prompt
_confirm() {
  read -p "Continue? [y/N] " -n 1 -r reply
  echo
  [[ $reply =~ ^[Yy]$ ]]
}

# Get worktree parent directory
_get_worktree_parent_dir() {
  local git_common_dir main_repo_root
  git_common_dir=$(realpath "$(git rev-parse --git-common-dir)")
  main_repo_root=$(dirname "$git_common_dir")
  dirname "$main_repo_root"
}

