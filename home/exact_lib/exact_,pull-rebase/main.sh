#!/usr/bin/env bash
# Description: Pull the latest changes from the remote and rebase

set -euo pipefail

# Source the utility library
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$script_dir/../shared/bash_utils_lib.sh"

current_branch=$(git branch --show-current)
upstream_remote=""
upstream_branch=""

# 1. Use tracking config (@{upstream}) — unambiguous, no grep needed.
# A slashless result means the branch tracks a local branch (branch.X.remote=".");
# fall through to step 2, which handles the "." remote correctly.
fork_upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2> /dev/null || true)
if [ -n "$fork_upstream" ] && [ "$fork_upstream" != "@{upstream}" ] && [ "${fork_upstream#*/}" != "$fork_upstream" ]; then
  upstream_remote="${fork_upstream%%/*}"
  upstream_branch="${fork_upstream#*/}"
fi

# 2. Fall back to branch.*.remote / branch.*.merge config.
if [ -z "$upstream_remote" ] || [ -z "$upstream_branch" ]; then
  cfg_remote=$(git config "branch.${current_branch}.remote" 2> /dev/null || true)
  cfg_merge=$(git config "branch.${current_branch}.merge" 2> /dev/null || true)
  if [ -n "$cfg_remote" ] && [ -n "$cfg_merge" ]; then
    upstream_remote="$cfg_remote"
    upstream_branch="${cfg_merge#refs/heads/}"
  fi
fi

# 3. Last resort: reflog (grep -m1 avoids multi-line matches).
if [ -z "$upstream_remote" ] || [ -z "$upstream_branch" ]; then
  fork_upstream=$(git reflog show "$current_branch" 2> /dev/null | grep -m1 'branch: Created from' | awk '{print $NF}' || true)
  # Only usable when it names an actual remote-tracking ref; a branch created
  # from a local ref yields a slashless name (e.g. "main"), which would
  # otherwise be misread as remote="main" branch="main".
  if [ -n "$fork_upstream" ] && [ "$fork_upstream" != "HEAD" ] && [ "${fork_upstream#*/}" != "$fork_upstream" ]; then
    if git remote get-url "${fork_upstream%%/*}" > /dev/null 2>&1; then
      upstream_remote="${fork_upstream%%/*}"
      upstream_branch="${fork_upstream#*/}"
    fi
  fi
fi

if [ -z "$upstream_remote" ] || [ -z "$upstream_branch" ]; then
  echo "Could not find $fork_upstream remote or branch"
  exit 1
fi

# ask for confirmation
echo "Pulling the latest changes from $upstream_remote/$upstream_branch and rebasing on top of it"

if ! _confirm; then
  exit 1
fi

git pull --rebase "$upstream_remote" "$upstream_branch"
