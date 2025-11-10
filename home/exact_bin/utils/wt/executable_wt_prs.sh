#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/../bash_utils_lib.sh"

show_usage() {
  cat <<EOF
Usage: f-wtree prs [-q|--quiet] [pr_number ...| search_terms]

Create worktrees from GitHub pull requests.

Arguments:
  [pr_number ...]   One or more PR numbers to create worktrees for
  [search_terms]    Search terms to find PRs (opens fzf selector)

Options:
  -q, --quiet       Suppress informational output
  -h, --help        Show this help message

Examples:
  f-wtree prs 123                    # Create worktree for PR #123
  f-wtree prs 123 456                # Create worktrees for PRs #123 and #456
  f-wtree prs feature authentication # Search PRs and select with fzf

Notes:
  - Automatically adds contributor's fork as a remote
  - Creates worktree using the PR's branch
  - If no arguments provided, opens interactive fzf search
EOF
}

quiet_mode=0
quiet_flag=()

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)
      show_usage
      exit 0
      ;;
    -q|--quiet)
      quiet_mode=1
      quiet_flag=(-q)
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

info() {
  if [ "$quiet_mode" -eq 0 ]; then
    printf '%s\n' "$@"
  fi
}

pr_numbers=()

if (($# > 0)); then
  all_numeric=true
  for arg in "$@"; do
    if [[ "$arg" =~ ^[0-9]+$ ]]; then
      pr_numbers+=("$arg")
    else
      all_numeric=false
      break
    fi
  done

  if ! $all_numeric; then
    pr_numbers=()
  fi
fi

if [ ${#pr_numbers[@]} -eq 0 ]; then
  search_query="$*"
  mapfile -t pr_numbers < <(gh pr list --search "${search_query}" --json number,title \
    --jq '.[] | "\(.number) \(.title)"' | fzf --multi --preview '
            gh pr view {1} --json number,title,body,author,labels,comments --template "
# PR #{{.number}}: {{.title}}

---

## Author: {{.author.login}}

{{range .labels}}- {{.name}} {{end}}

---


{{.body}}" | bat --style=auto --color always --wrap never --paging never --language Markdown
        ' --preview-window="right:70%:nowrap" --ansi | awk '{print $1}')
fi

if [ ${#pr_numbers[@]} -eq 0 ]; then
  echo "No PR selected." >&2
  exit 1
fi

for pr_number in "${pr_numbers[@]}"; do
  info "Processing PR #$pr_number..."

  pr_info=$(gh pr view "$pr_number" --json headRefName,headRepository,headRepositoryOwner \
    --jq '.headRefName + " " + .headRepository.name + " " + .headRepositoryOwner.login')

  branch_name=$(echo "$pr_info" | cut -d ' ' -f1)
  if [ -z "$branch_name" ]; then
    echo "No branch name found in PR #$pr_number info."
    continue
  fi

  repo_name=$(echo "$pr_info" | cut -d ' ' -f2)
  if [ -z "$repo_name" ]; then
    echo "No repository name found in PR #$pr_number info."
    continue
  fi

  repo_owner=$(echo "$pr_info" | cut -d ' ' -f3)
  if [ -z "$repo_owner" ]; then
    echo "No repository owner found in PR #$pr_number info."
    continue
  fi

  upstream_remote_owner=$(git remote get-url upstream | awk -F'[:/]' '{print $2}')

  if [ "$repo_owner" = "$upstream_remote_owner" ]; then
    info "PR #$pr_number is from the upstream repository. Setting the remote to 'upstream'..."
    repo_owner="upstream"
  fi

  repo_url="git@github.com:$repo_owner/$repo_name.git"

  if ! git remote get-url "$repo_owner" >/dev/null 2>&1; then
    git remote add "$repo_owner" "$repo_url"
  fi

  "$(dirname "$0")/wt_add.sh" "${quiet_flag[@]}" "$repo_owner/$branch_name"
  info "Completed PR #$pr_number worktree creation."
done
