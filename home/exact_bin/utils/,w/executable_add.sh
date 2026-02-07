#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/../bash_utils_lib.sh"
source "$(dirname "$0")/../worktree_lib.sh"

show_usage() {
  cat <<EOF
Usage: ,w add [-q|--quiet] <branch_name> [base_branch]

Add a git worktree for a branch.

Arguments:
  <branch_name>     Branch name to create worktree for. Can be:
                    - Local branch name (e.g., 'feature-branch')
                    - Remote branch (e.g., 'origin/feature-branch')
                    - Fork branch (e.g., 'username/feature-branch')
  [base_branch]     Optional base branch to create new branch from

Options:
  -q, --quiet       Suppress informational output
  -h, --help        Show this help message

Environment:
  COMMA_W_PRUNE=0   Disable automatic $(git worktree prune)

Examples:
  ,w add feature-branch
  ,w add origin/feature-branch
  ,w add username/feature-branch
  ,w add new-feature main
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

info() {
  if [ "$quiet_mode" -eq 0 ]; then
    printf '%s\n' "$@"
  fi
}

print_local_worktree_message() {
  if [ "$quiet_mode" -eq 0 ]; then
    local local_branch="$1"
    local local_path="$2"
    cat <<EOM

-------------

Created new worktree
For Local Branch: $local_branch
At Path: $local_path
EOM
  fi
}

git_worktree_add() {
  mkdir -p "$(dirname "$1")"
  if [ "$quiet_mode" -eq 1 ]; then
    git worktree add -q "$@"
  else
    git worktree add "$@"
  fi
}

git_fetch_ref() {
  if [ "$quiet_mode" -eq 1 ]; then
    git fetch --quiet "$@"
  else
    git fetch "$@"
  fi
}

remote_exists() {
  local remote="$1"
  git remote get-url "$remote" >/dev/null 2>&1
}

worktree_has_branch() {
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

any_remote_has_branch() {
  local branch="$1"
  local remote

  while IFS= read -r remote; do
    [ -z "$remote" ] && continue
    if git show-ref --verify --quiet "refs/remotes/${remote}/${branch}"; then
      return 0
    fi
  done < <(git remote)

  return 1
}

if [ $# -eq 0 ]; then
  show_usage
  exit 1
fi

branch_name="$1"
shift

is_base_branch_specified=0
base_branch=""

if [ $# -gt 1 ]; then
  show_usage
  exit 1
elif [ $# -eq 1 ]; then
  is_base_branch_specified=1
  base_branch="$1"
fi

parent_dir=$(_get_worktree_parent_dir)
parent_name=$(basename "$parent_dir")

_comma_w_prune_stale_worktrees "$quiet_mode"

if [ "$is_base_branch_specified" -eq 0 ]; then
  is_remote_branch_input=0
  input_remote=""
  input_remote_branch=""

  if [[ "$branch_name" == */* ]]; then
    input_remote="${branch_name%%/*}"
    input_remote_branch="${branch_name#*/}"
    if remote_exists "$input_remote"; then
      is_remote_branch_input=1
    fi
  fi

  if [ "$is_remote_branch_input" -eq 1 ]; then
    local_branch=""
    worktree_path=""

    if [ "$input_remote" = "origin" ] || [ "$input_remote" = "upstream" ]; then
      local_branch="$input_remote_branch"
      worktree_path="$parent_dir/$input_remote_branch"
    else
      local_branch="${input_remote}__${input_remote_branch}"
      worktree_path="$parent_dir/$input_remote/$input_remote_branch"
    fi

    if worktree_has_branch "$local_branch"; then
      info "Branch '$local_branch' already exists as a worktree."
      exit 0
    fi

    if ! git_fetch_ref "$input_remote" "$input_remote_branch"; then
      echo "Failed to fetch '${input_remote}/${input_remote_branch}' from remote '${input_remote}'." >&2
      exit 1
    fi
    if ! git show-ref --verify --quiet "refs/remotes/${input_remote}/${input_remote_branch}"; then
      echo "Remote branch '${input_remote}/${input_remote_branch}' not found." >&2
      exit 1
    fi

    if git show-ref --verify --quiet "refs/heads/$local_branch"; then
      info "Branch '$local_branch' already exists locally. Reusing it."
      git_worktree_add "$worktree_path" "$local_branch"
      _add_worktree_tmux_session "$quiet_mode" "$parent_name" "$local_branch" "$worktree_path"
      print_local_worktree_message "$local_branch" "$worktree_path"
    else
      git_worktree_add "$worktree_path" -b "$local_branch" "${input_remote}/${input_remote_branch}"
      _add_worktree_tmux_session "$quiet_mode" "$parent_name" "$local_branch" "$worktree_path"
      _print_created_worktree_message "$quiet_mode" "$local_branch" "$worktree_path" "${input_remote}/${input_remote_branch}"
    fi
  else
    worktree_path="$parent_dir/$branch_name"

    if worktree_has_branch "$branch_name"; then
      info "Branch '$branch_name' already exists as a worktree."
      exit 0
    fi

    if git show-ref --verify --quiet "refs/heads/$branch_name"; then
      info "Branch '$branch_name' already exists locally. Reusing it."
      git_worktree_add "$worktree_path" "$branch_name"
      _add_worktree_tmux_session "$quiet_mode" "$parent_name" "$branch_name" "$worktree_path"
      print_local_worktree_message "$branch_name" "$worktree_path"
    elif git show-ref --verify --quiet "refs/remotes/origin/$branch_name"; then
      git_worktree_add "$worktree_path" -b "$branch_name" "origin/$branch_name"
      _add_worktree_tmux_session "$quiet_mode" "$parent_name" "$branch_name" "$worktree_path"
      _print_created_worktree_message "$quiet_mode" "$branch_name" "$worktree_path" "origin/$branch_name"
    elif git show-ref --verify --quiet "refs/remotes/upstream/$branch_name"; then
      git_worktree_add "$worktree_path" -b "$branch_name" "upstream/$branch_name"
      _add_worktree_tmux_session "$quiet_mode" "$parent_name" "$branch_name" "$worktree_path"
      _print_created_worktree_message "$quiet_mode" "$branch_name" "$worktree_path" "upstream/$branch_name"
    else
      git_worktree_add "$worktree_path" -b "$branch_name"
      _add_worktree_tmux_session "$quiet_mode" "$parent_name" "$branch_name" "$worktree_path"
      _print_created_worktree_message "$quiet_mode" "$branch_name" "$worktree_path"
    fi
  fi
else
  inferred_branch_remote=""
  inferred_branch_name=""
  if [[ "$branch_name" == */* ]]; then
    inferred_branch_remote="${branch_name%%/*}"
    inferred_branch_name="${branch_name#*/}"
  fi

  if [ -n "$inferred_branch_remote" ] && remote_exists "$inferred_branch_remote"; then
    if [ "$inferred_branch_remote" = "origin" ] || [ "$inferred_branch_remote" = "upstream" ] || git show-ref --verify --quiet "refs/remotes/${inferred_branch_remote}/${inferred_branch_name}"; then
      echo "WHEN using base branch argument, main branch argument SHOULD NOT include a remote name. Please provide a valid branch name." >&2
      echo "For example, instead of ,w add $branch_name $base_branch, use ,w add $inferred_branch_name $base_branch." >&2
      exit 1
    fi
  fi

  if git show-ref --verify --quiet "refs/heads/$branch_name"; then
    echo "Branch '$branch_name' already exists locally." >&2
    echo "Cannot create a new branch with the same name." >&2
    exit 1
  fi
  if any_remote_has_branch "$branch_name"; then
    echo "Branch '$branch_name' already exists on a remote." >&2
    echo "Cannot create a new branch with the same name." >&2
    exit 1
  fi

  target_branch="$branch_name"
  base_ref=""
  worktree_path="$parent_dir/$branch_name"

  base_remote=""
  base_remote_branch=""
  if [[ "$base_branch" == */* ]]; then
    base_remote="${base_branch%%/*}"
    base_remote_branch="${base_branch#*/}"
    if remote_exists "$base_remote"; then
      if ! git_fetch_ref "$base_remote" "$base_remote_branch"; then
        echo "Failed to fetch '${base_remote}/${base_remote_branch}' from remote '${base_remote}'." >&2
        exit 1
      fi
      if ! git show-ref --verify --quiet "refs/remotes/${base_remote}/${base_remote_branch}"; then
        echo "Base branch '$base_branch' does not exist." >&2
        exit 1
      fi
      base_ref="${base_remote}/${base_remote_branch}"

      if [ "$base_remote" = "origin" ] || [ "$base_remote" = "upstream" ]; then
        target_branch="$branch_name"
        worktree_path="$parent_dir/$branch_name"
      else
        target_branch="${base_remote}__${branch_name}"
        worktree_path="$parent_dir/$base_remote/$branch_name"
      fi
    fi
  fi

  if [ -z "$base_ref" ]; then
    if git show-ref --verify --quiet "refs/heads/$base_branch"; then
      base_ref="$base_branch"
    elif git show-ref --verify --quiet "refs/remotes/origin/$base_branch"; then
      base_ref="origin/$base_branch"
    elif git show-ref --verify --quiet "refs/remotes/upstream/$base_branch"; then
      base_ref="upstream/$base_branch"
    elif git rev-parse --verify --quiet "${base_branch}^{commit}" >/dev/null; then
      base_ref="$base_branch"
    else
      echo "Base branch '$base_branch' does not exist." >&2
      exit 1
    fi
  fi

  if worktree_has_branch "$target_branch"; then
    info "Branch '$target_branch' already exists as a worktree."
    exit 0
  fi

  if git show-ref --verify --quiet "refs/heads/$target_branch"; then
    echo "Branch '$target_branch' already exists locally." >&2
    echo "Cannot create a new branch with the same name." >&2
    exit 1
  fi

  git_worktree_add "$worktree_path" -b "$target_branch" "$base_ref"
  _add_worktree_tmux_session "$quiet_mode" "$parent_name" "$target_branch" "$worktree_path"
  _print_created_worktree_message "$quiet_mode" "$target_branch" "$worktree_path" "$base_ref"
fi

if command -v zoxide &>/dev/null; then
  zoxide add "$worktree_path" 2>/dev/null || true
fi
