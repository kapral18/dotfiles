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

parse_owner_repo_from_remote_url() {
  local url="$1"
  local path=""

  url="${url%.git}"
  case "$url" in
    git@github.com:*)
      path="${url#git@github.com:}"
      ;;
    ssh://git@github.com/*)
      path="${url#ssh://git@github.com/}"
      ;;
    https://github.com/*)
      path="${url#https://github.com/}"
      ;;
    http://github.com/*)
      path="${url#http://github.com/}"
      ;;
    *)
      return 1
      ;;
  esac

  if [[ "$path" != */* ]]; then
    return 1
  fi

  printf '%s\t%s\n' "${path%%/*}" "${path#*/}"
}

get_base_repo_owner_and_name() {
  local base_info remote_url parsed

  base_info="$(gh repo view --json owner,name --jq '[.owner.login, .name] | @tsv' 2>/dev/null || true)"
  if [ -n "$base_info" ]; then
    printf '%s\n' "$base_info"
    return 0
  fi

  remote_url="$(git remote get-url upstream 2>/dev/null || git remote get-url origin 2>/dev/null || true)"
  if [ -z "$remote_url" ]; then
    return 1
  fi

  if parsed="$(parse_owner_repo_from_remote_url "$remote_url")"; then
    printf '%s\n' "$parsed"
    return 0
  fi

  return 1
}

get_base_remote_name() {
  if git remote get-url upstream >/dev/null 2>&1; then
    echo "upstream"
  elif git remote get-url origin >/dev/null 2>&1; then
    echo "origin"
  else
    echo ""
  fi
}

show_usage() {
  cat <<EOF
Usage: ,w prs [-q|--quiet] [--focus] [pr_number ...| search_terms]

Create worktrees from GitHub pull requests.

Arguments:
  [pr_number ...]   One or more PR numbers to create worktrees for
  [search_terms]    Search terms to find PRs (opens fzf selector)

Options:
  -q, --quiet       Suppress informational output
  --focus           Switch/attach to the created worktree's tmux session
  -h, --help        Show this help message

Examples:
  ,w prs 123                    # Create worktree for PR #123
  ,w prs 123 456                # Create worktrees for PRs #123 and #456
  ,w prs feature authentication # Search PRs and select with fzf

Notes:
  - Automatically adds contributor's fork as a remote
  - Default behavior creates a stable local branch name: pr-<number>
  - If no arguments provided, opens interactive fzf search
EOF
}

quiet_mode=0
quiet_flag=()
focus_mode=0

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
    --focus)
      focus_mode=1
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

require_cmd gh

info() {
  if [ "$quiet_mode" -eq 0 ]; then
    printf '%s\n' "$@"
  fi
}

git_fetch_ref() {
  if [ "$quiet_mode" -eq 1 ]; then
    git fetch --quiet "$@"
  else
    git fetch "$@"
  fi
}

normalize_pr_number() {
  local input="$1"
  local pr_number=""

  if [[ "$input" =~ ^#[0-9]+$ ]]; then
    pr_number="${input#\#}"
  elif [[ "$input" =~ ^[0-9]+$ ]]; then
    pr_number="$input"
  elif [[ "$input" =~ /pull/([0-9]+) ]]; then
    pr_number="${BASH_REMATCH[1]}"
  else
    return 1
  fi

  printf '%s\n' "$pr_number"
}

pr_numbers=()

if (($# > 0)); then
  all_pr_ids=true
  for arg in "$@"; do
    if pr="$(normalize_pr_number "$arg")"; then
      pr_numbers+=("$pr")
    else
      all_pr_ids=false
      break
    fi
  done

  if ! $all_pr_ids; then
    pr_numbers=()
  fi
fi

if [ ${#pr_numbers[@]} -eq 0 ]; then
  require_cmd fzf
  require_cmd bat
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

if ! IFS=$'\t' read -r base_owner base_repo < <(get_base_repo_owner_and_name); then
  echo "Failed to determine base repository owner/name." >&2
  exit 1
fi

base_remote="$(get_base_remote_name)"

parent_dir=$(_get_worktree_parent_dir)
parent_name=$(basename "$parent_dir")

_comma_w_prune_stale_worktrees "$quiet_mode"

for pr_number in "${pr_numbers[@]}"; do
  info "Processing PR #$pr_number..."

  if ! IFS=$'\t' read -r branch_name repo_name repo_owner < <(gh pr view "$pr_number" \
    --json headRefName,headRepository,headRepositoryOwner \
    --jq '[.headRefName, .headRepository.name, .headRepositoryOwner.login] | @tsv'); then
    echo "Failed to fetch PR #$pr_number metadata." >&2
    continue
  fi

  if [ -z "$branch_name" ] || [ -z "$repo_name" ] || [ -z "$repo_owner" ]; then
    echo "Incomplete PR #$pr_number metadata." >&2
    continue
  fi

  remote_name="$repo_owner"
  if [ "$repo_owner" = "$base_owner" ] && [ "$repo_name" = "$base_repo" ]; then
    if [ -z "$base_remote" ]; then
      echo "PR #$pr_number targets the base repo, but neither 'upstream' nor 'origin' remote exists." >&2
      continue
    fi
    remote_name="$base_remote"
  else
    repo_url="git@github.com:$repo_owner/$repo_name.git"
    if ! git remote get-url "$remote_name" >/dev/null 2>&1; then
      git remote add "$remote_name" "$repo_url"
    fi
  fi

  local_branch="pr-$pr_number"
  existing_path="$(_comma_w_find_worktree_path_for_branch "$local_branch" 2>/dev/null || true)"
  if [ -n "$existing_path" ]; then
    info "Worktree already exists for '$local_branch'."
    if [ "$focus_mode" -eq 1 ]; then
      _add_worktree_tmux_session "$quiet_mode" "$parent_name" "$local_branch" "$existing_path"
      _comma_w_focus_tmux_session "$quiet_mode" "$(_comma_w_tmux_session_name "$parent_name" "$local_branch")" "$existing_path" || true
    fi
    info "Completed PR #$pr_number worktree creation."
    continue
  fi

  if ! git_fetch_ref "$remote_name" "$branch_name"; then
    echo "Failed to fetch '${remote_name}/${branch_name}' from remote '${remote_name}'." >&2
    continue
  fi
  if ! git show-ref --verify --quiet "refs/remotes/${remote_name}/${branch_name}"; then
    echo "Remote branch '${remote_name}/${branch_name}' not found." >&2
    continue
  fi

  base_ref="refs/remotes/${remote_name}/${branch_name}"
  "$(dirname "$0")/wt_add.sh" "${quiet_flag[@]}" "$local_branch" "$base_ref"

  if [ "$focus_mode" -eq 1 ]; then
    worktree_path="$(_comma_w_find_worktree_path_for_branch "$local_branch" || true)"
    if [ -n "$worktree_path" ]; then
      _add_worktree_tmux_session "$quiet_mode" "$parent_name" "$local_branch" "$worktree_path"
      _comma_w_focus_tmux_session "$quiet_mode" "$(_comma_w_tmux_session_name "$parent_name" "$local_branch")" "$worktree_path" || true
    fi
  fi

  info "Completed PR #$pr_number worktree creation."
done
