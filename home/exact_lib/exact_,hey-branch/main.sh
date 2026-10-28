#!/usr/bin/env bash
# Description: Check the status of the current branch

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$script_dir/../shared/bash_utils_lib.sh"

current_branch=$(git branch --show-current)

remote_branch=$(git rev-parse --abbrev-ref "$current_branch"@{upstream} 2> /dev/null || true)

echo ------------------------------------

if [ -z "$remote_branch" ]; then
  echo "Tracked Branch: <missing>"
  exit 1
fi

remote_branch_remote=$(echo "$remote_branch" | cut -d'/' -f1)
remote_branch_name=$(echo "$remote_branch" | cut -d'/' -f2-)

echo "Tracked Branch: '$remote_branch'"

echo ------------------------------------

git fetch "$remote_branch_remote" "$remote_branch_name" 2> /dev/null

if git ls-remote --exit-code --heads "$remote_branch_remote" "$remote_branch_name" > /dev/null 2>&1; then
  echo "Tracked Branch Exists: Yes"
  echo ------------------------------------

  local_commit=$(git rev-parse HEAD)
  remote_commit=$(git rev-parse "$remote_branch")

  if [ "$local_commit" = "$remote_commit" ]; then
    echo "Local Branch In Sync: Yes"
  else
    behind=$(git rev-list --count "HEAD..$remote_branch")
    ahead=$(git rev-list --count "$remote_branch..HEAD")
    echo "Local Branch In Sync: No

Behind: $behind commits
Ahead: $ahead commits"
  fi
else
  echo "Tracked Branch Exists: No"
fi

echo ------------------------------------
