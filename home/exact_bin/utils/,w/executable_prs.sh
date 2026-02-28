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
Usage: ,w prs [-q|--quiet] [--focus] [--awaiting] [pr_number ...| search_terms]

Create worktrees from GitHub pull requests.

Arguments:
  [pr_number ...]   One or more PR numbers to create worktrees for
  [search_terms]    Search terms to find PRs (opens fzf selector)

Options:
  -q, --quiet       Suppress informational output
  --focus           Switch/attach to the created worktree's tmux session
  --awaiting        List PRs awaiting my/team review (autocomplete: last 7 days)
  -h, --help        Show this help message

Examples:
  ,w prs 123                    # Create worktree for PR #123
  ,w prs 123 456                # Create worktrees for PRs #123 and #456
  ,w prs feature authentication # Search PRs and select with fzf
  ,w prs --awaiting             # Pick from PRs awaiting my/team review

Notes:
  - Automatically adds contributor's fork as a remote
  - Default behavior creates a stable local branch name based on PR head: <remote>__<branch>
  - Worktrees are created under <remote>/<branch> to keep paths readable
  - If no arguments provided, opens interactive fzf search
EOF
}

quiet_mode=0
quiet_flag=()
focus_mode=0
awaiting_mode=0
complete_mode=0

awaiting_days_default=7
awaiting_days="${COMMA_W_AWAITING_DAYS:-$awaiting_days_default}"

while [ $# -gt 0 ]; do
  case "$1" in
  -h | --help)
    show_usage
    exit 0
    ;;
  -q | --quiet)
    quiet_mode=1
    quiet_flag=(-q)
    shift
    ;;
  --focus)
    focus_mode=1
    shift
    ;;
  --awaiting)
    awaiting_mode=1
    shift
    ;;
  --complete)
    # Internal: print completion candidates (number<TAB>title) and exit.
    complete_mode=1
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

get_user_login() {
  gh api user --jq '.login' 2>/dev/null || true
}

_iso_date_days_ago() {
  local days="$1"

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$days" <<'PY'
import datetime
import sys

days = int(sys.argv[1])
dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
print(dt.strftime('%Y-%m-%d'))
PY
    return 0
  fi

  if command -v gdate >/dev/null 2>&1; then
    gdate -u -d "${days} days ago" +%Y-%m-%d
    return 0
  fi

  date -u -d "${days} days ago" +%Y-%m-%d
}

_comma_w_collect_team_review_filters() {
  local org_owner="$1"
  local config_file="${GH_DASH_CONFIG:-$HOME/.config/gh-dash/config.yml}"

  if [ ! -f "$config_file" ]; then
    return 0
  fi

  # Parse strings like: team-review-requested:elastic/kibana-management.
  # Important: grep returns 1 when there are no matches; don't treat that as a fatal error.
  local matches=""
  matches="$(grep -Eo 'team-review-requested:[^ ]+' "$config_file" 2>/dev/null || true)"
  if [ -z "${matches}" ]; then
    return 0
  fi

  printf '%s\n' "${matches}" |
    sed 's/^team-review-requested://' |
    awk -v org="${org_owner}/" '$0 ~ "^"org {print $0}' |
    sort -u
}

_comma_w_build_awaiting_search_query() {
  local user_login="$1"
  local base_owner="$2"
  local since_date="$3"
  local extra_terms="$4"

  local -a ors
  ors+=("review-requested:${user_login}")

  local team
  while IFS= read -r team; do
    [ -n "$team" ] || continue
    ors+=("team-review-requested:${team}")
  done < <(_comma_w_collect_team_review_filters "$base_owner")

  local or_query=""
  local i
  for ((i = 0; i < ${#ors[@]}; i++)); do
    if [ $i -eq 0 ]; then
      or_query="${ors[$i]}"
    else
      or_query="${or_query} OR ${ors[$i]}"
    fi
  done

  # Exclude drafts, my own PRs, and PRs I've already reviewed.
  # Note: we also filter drafts client-side in _comma_w_list_prs_tsv to avoid
  # showing draft PRs if the search qualifier isn't applied as expected.
  # Time window is optional; we keep it for autocomplete, but not for fzf mode.
  local updated_clause=""
  if [ -n "${since_date}" ]; then
    updated_clause="updated:>=${since_date} "
  fi

  local query="is:open is:pr -is:draft ${updated_clause}-author:${user_login} -reviewed-by:${user_login} (${or_query})"
  if [ -n "${extra_terms//[[:space:]]/}" ]; then
    query="${query} ${extra_terms}"
  fi

  printf '%s\n' "$query"
}

_comma_w_list_prs_tsv() {
  # Prints: number<TAB>updated_day<TAB>title
  local search_query="$1"
  local exclude_drafts="${2:-0}"

  if [ "$exclude_drafts" -eq 1 ]; then
    gh pr list --search "${search_query}" --limit 200 --json number,title,updatedAt,isDraft \
      --jq 'map(select(.isDraft == false)) | sort_by(.updatedAt) | reverse | .[] | [(.number|tostring), (.updatedAt[0:10]), .title] | @tsv' 2>/dev/null || true
    return 0
  fi

  gh pr list --search "${search_query}" --limit 200 --json number,title,updatedAt \
    --jq 'sort_by(.updatedAt) | reverse | .[] | [(.number|tostring), (.updatedAt[0:10]), .title] | @tsv' 2>/dev/null || true
}

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

if [ "$complete_mode" -eq 1 ]; then
  if [ "$awaiting_mode" -eq 1 ]; then
    user_login="$(get_user_login)"
    if [ -z "$user_login" ]; then
      exit 0
    fi

    if ! IFS=$'\t' read -r base_owner _base_repo < <(get_base_repo_owner_and_name); then
      exit 0
    fi

    since_date="$(_iso_date_days_ago "$awaiting_days")"
    awaiting_query="$(_comma_w_build_awaiting_search_query "$user_login" "$base_owner" "$since_date" "")"
    _comma_w_list_prs_tsv "$awaiting_query" 1 | awk -F $'\t' '{print $1"\t"$3}'
    exit 0
  fi

  gh pr list --limit 200 --json number,title --jq '.[] | "\(.number)\t\(.title)"' 2>/dev/null || true
  exit 0
fi

if [ ${#pr_numbers[@]} -eq 0 ]; then
  require_cmd fzf
  require_cmd bat

  if [ "$awaiting_mode" -eq 1 ]; then
    user_login="$(get_user_login)"
    if [ -z "$user_login" ]; then
      echo "Failed to determine GitHub user login (are you authenticated?)." >&2
      exit 1
    fi

    if ! IFS=$'\t' read -r base_owner _base_repo < <(get_base_repo_owner_and_name); then
      echo "Failed to determine base repository owner/name." >&2
      exit 1
    fi

    extra_terms="$*"
    search_query="$(_comma_w_build_awaiting_search_query "$user_login" "$base_owner" "" "$extra_terms")"
  else
    search_query="$*"
  fi

  exclude_drafts=0
  if [ "$awaiting_mode" -eq 1 ]; then
    exclude_drafts=1
  fi

  mapfile -t pr_numbers < <(
    _comma_w_list_prs_tsv "$search_query" "$exclude_drafts" |
      fzf --multi --delimiter=$'\t' --with-nth=1,2,3 --preview '
            gh pr view {1} --json number,title,body,author,labels,comments,createdAt,updatedAt,reviewDecision --template "
# PR #{{.number}}: {{.title}}

---

## Dates

- Created: {{.createdAt}}
- Updated: {{.updatedAt}}

## Review

- Decision: {{.reviewDecision}}

---

## Author: {{.author.login}}

{{range .labels}}- {{.name}} {{end}}

---

{{.body}}" | bat --style=auto --color always --wrap never --paging never --language Markdown
        ' --preview-window="right:70%:nowrap" --ansi |
      awk -F $'\t' '{print $1}'
  )
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

  if [ "$remote_name" = "origin" ] || [ "$remote_name" = "upstream" ]; then
    local_branch="$branch_name"
    worktree_path="$parent_dir/$branch_name"
  else
    local_branch="${remote_name}__${branch_name}"
    worktree_path="$parent_dir/$remote_name/$branch_name"
  fi

  # If this PR was previously checked out using a pr-<number> branch name,
  # rename/move it to the current naming scheme to avoid duplicate worktrees.
  old_local_branch="pr-$pr_number"
  if [ "$old_local_branch" != "$local_branch" ]; then
    old_existing_path="$(_comma_w_find_worktree_path_for_branch "$old_local_branch" 2>/dev/null || true)"
    if [ -n "$old_existing_path" ]; then
      existing_path="$(_comma_w_find_worktree_path_for_branch "$local_branch" 2>/dev/null || true)"
      if [ -z "$existing_path" ]; then
        info "Migrating existing worktree '$old_local_branch' -> '$local_branch'..."
        mv_args=()
        if [ "$quiet_mode" -eq 1 ]; then
          mv_args+=(--quiet)
        fi
        if [ "$focus_mode" -eq 1 ]; then
          mv_args+=(--focus)
        fi
        "$(dirname "$0")/mv.sh" "${mv_args[@]}" --path "$worktree_path" "$old_local_branch" "$local_branch" >/dev/null || true
      fi
    fi
  fi

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

  base_ref="${remote_name}/${branch_name}"

  mkdir -p "$(dirname "$worktree_path")"
  if git show-ref --verify --quiet "refs/heads/$local_branch"; then
    if [ "$quiet_mode" -eq 1 ]; then
      git worktree add -q "$worktree_path" "$local_branch"
    else
      git worktree add "$worktree_path" "$local_branch"
    fi
  else
    if [ "$quiet_mode" -eq 1 ]; then
      git worktree add -q "$worktree_path" -b "$local_branch" "$base_ref"
    else
      git worktree add "$worktree_path" -b "$local_branch" "$base_ref"
    fi
  fi

  _add_worktree_tmux_session "$quiet_mode" "$parent_name" "$local_branch" "$worktree_path"
  _print_created_worktree_message "$quiet_mode" "$local_branch" "$worktree_path" "$base_ref"

  # Native Git Smart Push Routing for prefixed branches
  if [[ "$local_branch" == *__* ]] && [ "$remote_name" != "origin" ] && [ "$remote_name" != "upstream" ]; then
    git config extensions.worktreeConfig true
    git -C "$worktree_path" config --worktree remote.pushDefault "$remote_name"
    git -C "$worktree_path" config --worktree push.default upstream
    info "Configured per-worktree smart push routing -> $remote_name"
  fi

  if command -v zoxide &>/dev/null; then
    zoxide add "$worktree_path" 2>/dev/null || true
  fi

  if [ "$focus_mode" -eq 1 ]; then
    _comma_w_focus_tmux_session "$quiet_mode" "$(_comma_w_tmux_session_name "$parent_name" "$local_branch")" "$worktree_path" || true
  fi

  info "Completed PR #$pr_number worktree creation."
done
