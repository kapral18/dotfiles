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
Usage: ,w remove [--tmux-notify] [--paths <path...>]

Interactively remove git worktrees.

Options:
  -h, --help        Show this help message
  --paths           Remove specific worktree path(s) (skip interactive picker)
  --tmux-notify     If running inside tmux, show progress via tmux messages

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
  - If you have stale worktree metadata, run $(,w prune) first
EOF
}

tmux_notify=0
paths_mode=0
paths=()

while [ $# -gt 0 ]; do
  case "$1" in
  -h | --help)
    show_usage
    exit 0
    ;;
  --tmux-notify)
    tmux_notify=1
    shift
    ;;
  --paths)
    paths_mode=1
    shift
    while [ $# -gt 0 ]; do
      case "$1" in
      --)
        shift
        break
        ;;
      -*)
        break
        ;;
      *)
        paths+=("$1")
        shift
        ;;
      esac
    done
    ;;
  *)
    echo "Error: Unknown option '$1'" >&2
    show_usage
    exit 1
    ;;
  esac
done

default_branch=$(git config --get init.defaultbranch || echo "main")

parent_dir=$(_get_worktree_parent_dir)
parent_name=$(basename "$parent_dir")

notify() {
  local msg="$1"
  echo "$msg"
  if [ "$tmux_notify" -eq 1 ] && [ -n "${TMUX:-}" ] && command -v tmux >/dev/null 2>&1; then
    tmux display-message -d 6000 "$msg" 2>/dev/null || true
  fi
}

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

worktrees=()
if [ "$paths_mode" -eq 1 ]; then
  if [ ${#paths[@]} -eq 0 ]; then
    echo "No paths provided."
    exit 1
  fi

  find_branch_for_path() {
    local needle="$1"
    local line p b
    for line in "${selectable_worktrees[@]}"; do
      IFS=$'\t' read -r p b <<<"$line"
      [ -n "$p" ] || continue
      if [ "$p" = "$needle" ]; then
        printf '%s\n' "$b"
        return 0
      fi
    done
    return 1
  }

  for p in "${paths[@]}"; do
    p="$(realpath "$p" 2>/dev/null || printf '%s' "$p")"
    b="$(find_branch_for_path "$p" || true)"
    if [ -z "${b}" ]; then
      notify "Skipping (not removable or not found): $p"
      continue
    fi
    worktrees+=("${p}"$'\t'"${b}")
  done
else
  require_cmd fzf
  mapfile -t worktrees < <(printf '%s\n' "${selectable_worktrees[@]}" | fzf --no-preview --multi)
fi

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

  notify "Removing worktree: $worktree_path ($worktree_branch)"
  if ! git worktree remove "$worktree_path"; then
    notify "Failed to remove worktree: $worktree_path"
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

  _bag_and_rmdir_upwards_ignoring_ds_store "$(dirname "$worktree_path")" "$parent_dir"

  if command -v zoxide &>/dev/null; then
    zoxide remove "$worktree_path"
  fi

  notify "Removed worktree: $worktree_path ($worktree_branch)"
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
