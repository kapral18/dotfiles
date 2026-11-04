#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$script_dir/../shared/bash_utils_lib.sh"
source "$script_dir/../shared/worktree_lib.sh"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" > /dev/null 2>&1; then
    echo "Missing required dependency: '$cmd'." >&2
    exit 1
  fi
}

# Split a tab-separated record into named variables without collapsing empty
# fields. Bash treats tab as IFS whitespace, so `IFS=$'\t' read` merges
# consecutive tabs and shifts later columns (empty branch_ref on a detached
# worktree made detached=1 land in branch_ref and the remove path skip it).
_tsv_assign() {
  local _line="$1"
  shift
  local _mapped
  _mapped="$(printf '%s' "$_line" | tr '\t' '\037')"
  # Trailing newline so `read` does not fail-closed under `set -e` on EOF.
  IFS=$'\037' read -r "$@" < <(printf '%s\n' "$_mapped") || true
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
  cat << 'EOF'
Usage: ,w remove [--tmux-notify] [--paths <path...>]

Interactively remove git worktrees.

Options:
  -h, --help        Show this help message
  --paths           Remove specific worktree path(s) (skip interactive picker)
  --force           Bypass unsaved-work and submodule-history safeguards
  --preflight       With --paths: only print paths that would be skipped, remove nothing
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
  - Interactive mode skips detached HEAD worktrees; --paths removes them
  - If you have stale worktree metadata, run ,w prune first
EOF
}

tmux_notify=0
paths_mode=0
force_remove=0
preflight_mode=0
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
    --force)
      force_remove=1
      shift
      ;;
    --preflight)
      preflight_mode=1
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

notify() {
  local msg="$1"
  echo "$msg"
  if [ "$tmux_notify" -eq 1 ] && [ -n "${TMUX:-}" ] && command -v tmux > /dev/null 2>&1; then
    tmux display-message -d 6000 "$msg" 2> /dev/null || true
  fi
}

_check_worktree_safe_to_remove() {
  local path="$1"
  local issues=()

  local top branch_ref ref unsafe_commits dirty_files
  top="$(git -C "$path" rev-parse --show-toplevel 2> /dev/null)" || return 1
  [ "$(realpath "$path" 2> /dev/null)" = "$(realpath "$top" 2> /dev/null)" ] || return 1
  dirty_files="$(git -C "$path" status --porcelain -unormal 2> /dev/null)" || return 1
  if [ -n "$dirty_files" ]; then
    issues+=("uncommitted or untracked files")
  fi

  local main_path
  main_path="$(git -C "$path" worktree list --porcelain | sed -n 's/^worktree //p' | head -n 1)"
  if [ "$(realpath "$main_path" 2> /dev/null)" = "$(realpath "$path" 2> /dev/null)" ]; then
    python3 "$script_dir/../shared/worktree_nested_git.py" "$path" --all-worktrees || return 1
    unsafe_commits="$(git -C "$path" rev-list --all HEAD --not --remotes 2> /dev/null)" || return 1
  else
    python3 "$script_dir/../shared/worktree_nested_git.py" "$path" || return 1
    branch_ref="$(git -C "$path" symbolic-ref -q HEAD 2> /dev/null || true)"
    local -a retained_refs=()
    while IFS= read -r ref; do
      [ "$ref" = "$branch_ref" ] || retained_refs+=("$ref")
    done < <(git -C "$path" for-each-ref --format='%(refname)')
    unsafe_commits="$(git -C "$path" rev-list HEAD --not "${retained_refs[@]}" 2> /dev/null)" || return 1
  fi

  if [ -n "$unsafe_commits" ]; then
    issues+=("commits not reachable from retained refs")
  fi

  if [ ${#issues[@]} -gt 0 ]; then
    notify "Skipping worktree with unsaved work: $path (use --force to override)"
    for issue in "${issues[@]}"; do
      echo "  $issue" >&2
    done
    return 1
  fi
  return 0
}

# --preflight: report-only mode for callers (e.g. the tmux picker) that need to
# know which paths would be skipped BEFORE they take their own destructive
# steps (killing sessions, tombstoning picker rows). Prints each unsafe input
# path to stdout, one per line, and exits without removing anything. Runs
# before any repo-context detection so it works from any cwd.
if [ "$preflight_mode" -eq 1 ]; then
  if [ "$paths_mode" -ne 1 ]; then
    echo "--preflight requires --paths" >&2
    exit 1
  fi
  for p in "${paths[@]}"; do
    wp="$(realpath "$p" 2> /dev/null || printf '%s' "$p")"
    if ! _check_worktree_safe_to_remove "$wp" 2> /dev/null > /dev/null; then
      printf '%s\n' "$p"
    fi
  done
  exit 0
fi

default_branch="$(_comma_w_detect_default_branch)"

parent_dir=$(_get_worktree_parent_dir)
parent_name="$(_comma_w_tmux_parent_name_from_dir "$parent_dir")"

main_worktree="$(list_worktrees_porcelain | awk -F'\t' 'NR == 1 { print $1 }')"
main_worktree_rp="$(realpath "$main_worktree" 2> /dev/null || printf '%s' "$main_worktree")"

selectable_worktrees=()
while IFS= read -r _line; do
  [ -n "$_line" ] || continue
  selectable_worktrees+=("$_line")
done < <(
  list_worktrees_porcelain | awk -F'\t' -v default_branch="$default_branch" '
    NR == 1 { next }
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

if [ ${#selectable_worktrees[@]} -eq 0 ] && [ "$paths_mode" -ne 1 ]; then
  echo "No removable worktrees found."
  exit 1
fi

worktrees=()
if [ "$paths_mode" -eq 1 ]; then
  if [ ${#paths[@]} -eq 0 ]; then
    echo "No paths provided."
    exit 1
  fi

  find_record_for_path() {
    local needle="$1"
    local needle_rp
    needle_rp="$(realpath "$needle" 2> /dev/null || printf '%s' "$needle")"
    local line p branch_ref detached locked p_rp
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      _tsv_assign "$line" p branch_ref detached locked
      [ -n "$p" ] || continue
      p_rp="$(realpath "$p" 2> /dev/null || printf '%s' "$p")"
      if [ "$p" = "$needle" ] || [ "$p_rp" = "$needle" ] || [ "$p" = "$needle_rp" ] || [ "$p_rp" = "$needle_rp" ]; then
        printf '%s\t%s\t%s\t%s\n' "$p" "$branch_ref" "$detached" "$locked"
        return 0
      fi
    done < <(list_worktrees_porcelain)
    return 1
  }

  for p in "${paths[@]}"; do
    p="$(realpath "$p" 2> /dev/null || printf '%s' "$p")"
    rec="$(find_record_for_path "$p" || true)"
    if [ -z "${rec}" ]; then
      notify "Skipping (not a git worktree path): $p"
      continue
    fi
    _tsv_assign "$rec" p_found branch_ref detached locked
    if [ "$(realpath "$p_found" 2> /dev/null || printf '%s' "$p_found")" = "$main_worktree_rp" ]; then
      notify "Skipping main worktree: $p_found"
      continue
    fi
    case "$locked" in
      1)
        notify "Skipping locked worktree: $p_found"
        continue
        ;;
    esac

    branch=""
    case "$branch_ref" in
      refs/heads/*) branch="${branch_ref#refs/heads/}" ;;
    esac

    # Explicit paths: allow removing detached worktrees too.
    if [ -z "$branch" ]; then
      case "$detached" in
        1) ;;
        *)
          notify "Skipping (not a local branch worktree): $p_found"
          continue
          ;;
      esac
    fi

    if [ -n "$branch" ] && [ "$branch" = "$default_branch" ]; then
      notify "Skipping default branch worktree: $p_found ($branch)"
      continue
    fi

    worktrees+=("${p_found}"$'\t'"${branch}"$'\t'"${detached}")
  done
else
  require_cmd fzf
  worktrees=()
  while IFS= read -r _line; do
    [ -n "$_line" ] || continue
    worktrees+=("$_line")
  done < <(printf '%s\n' "${selectable_worktrees[@]}" | fzf --no-preview --multi)
fi

if [ ${#worktrees[@]} -eq 0 ]; then
  echo "No worktrees selected."
  exit 1
fi

remotes_to_check=()

_get_branch_upstream_remote() {
  local branch="$1"
  local remote

  remote="$(git for-each-ref --format='%(upstream:remotename)' "refs/heads/$branch" 2> /dev/null || true)"
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
      if git remote get-url "$candidate" > /dev/null 2>&1; then
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
  _tsv_assign "$worktree" worktree_path worktree_branch worktree_detached

  if [ "$force_remove" -eq 0 ]; then
    if ! _check_worktree_safe_to_remove "$worktree_path"; then
      continue
    fi
  fi

  if [ -n "${worktree_detached:-}" ] && [ "$worktree_detached" = "1" ]; then
    notify "Removing detached worktree: $worktree_path"
  else
    notify "Removing worktree: $worktree_path ($worktree_branch)"
  fi
  if ! git worktree remove --force "$worktree_path"; then
    notify "Failed to remove worktree: $worktree_path"
    # Fall through to the rm -rf fallback below. `git worktree remove --force`
    # cleans the .git/worktrees/<name>/ metadata before the on-disk delete, so
    # a failure here typically means the dir is leftover (Permission denied,
    # ENOTEMPTY race on macOS, etc.) while git's own bookkeeping is consistent.
  fi

  # `git worktree remove` can refuse to delete the directory if there are
  # leftovers (permissions, races, etc.). Those should not be moved into `.bag`
  # as a pseudo-worktree; delete the worktree dir itself and only bag leftover
  # *intermediate* directories between the wrapper and the worktree path.
  worktree_path_rp="$(realpath "$worktree_path" 2> /dev/null || printf '%s' "$worktree_path")"
  if [ -e "$worktree_path_rp" ]; then
    case "$worktree_path_rp" in
      "" | "/" | "$HOME")
        notify "Refusing to delete unsafe path: $worktree_path_rp"
        continue
        ;;
    esac
    if [ "$worktree_path_rp" = "$main_worktree_rp" ] || [ -d "$worktree_path_rp/.git" ]; then
      notify "Refusing to delete main worktree: $worktree_path_rp"
      continue
    fi
    notify "Worktree dir still exists; deleting: $worktree_path_rp"
    rm -rf "$worktree_path_rp" 2> /dev/null || true
  fi

  if [ -n "${worktree_detached:-}" ] && [ "$worktree_detached" = "1" ]; then
    _remove_worktree_tmux_session 0 "$worktree_path" ""
  else
    remote="$(_get_branch_upstream_remote "$worktree_branch")"
    if [ -z "$remote" ]; then
      remote="$(_infer_remote_from_prefixed_branch "$worktree_branch")"
    fi
    if [ -n "$remote" ] && ! _comma_w_remote_is_first_party "$remote"; then
      remotes_to_check+=("$remote")
    fi

    if worktree_branch_in_use "$worktree_branch"; then
      echo "Branch '$worktree_branch' is still used by other worktrees, skipping deletion."
    else
      git branch -D "$worktree_branch"
    fi

    _remove_worktree_tmux_session 0 "$worktree_path" "$(_comma_w_tmux_session_name "$parent_name" "$worktree_branch")"
  fi

  _bag_and_rmdir_upwards_ignoring_ds_store "$(dirname "$worktree_path")" "$parent_dir"

  if command -v zoxide &> /dev/null; then
    zoxide remove "$worktree_path" 2> /dev/null || true
  fi

  notify "Removed worktree: $worktree_path ($worktree_branch)"
done

if [ ${#remotes_to_check[@]} -gt 0 ]; then
  _remote_exists() {
    local remote="$1"
    git remote get-url "$remote" > /dev/null 2>&1
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
      "" | .)
        continue
        ;;
    esac
    if _comma_w_remote_is_first_party "$remote"; then
      continue
    fi

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
