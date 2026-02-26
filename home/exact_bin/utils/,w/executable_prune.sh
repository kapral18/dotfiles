#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/../bash_utils_lib.sh"

show_usage() {
  cat <<EOF
Usage: ,w prune [-q|--quiet] [--apply] [--all]

Prune stale worktree metadata and (optionally) kill stale tmux sessions.

Options:
  -q, --quiet       Suppress informational output
  --apply           Apply changes (default is dry-run output only)
  --all             Consider tmux sessions across all repos (not just this repo's ,w sessions)
  -h, --help        Show this help message
EOF
}

quiet_mode=0
apply_mode=0
all_mode=0

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
  --apply)
    apply_mode=1
    shift
    ;;
  --all)
    all_mode=1
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
    echo "Error: Unknown argument '$1'." >&2
    show_usage
    exit 1
    ;;
  esac
done

in_git_repo=0
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  in_git_repo=1
fi

parent_name=""
if [ "$in_git_repo" -eq 1 ]; then
  parent_dir=$(_get_worktree_parent_dir)
  parent_name=$(basename "$parent_dir")
fi

git_has_stale=0
tmux_has_stale=0

if [ "$in_git_repo" -eq 1 ]; then
  dry_run_output="$(git worktree prune --dry-run 2>&1 || true)"
  if [ -n "${dry_run_output//[[:space:]]/}" ]; then
    git_has_stale=1
  fi
else
  if [ "$all_mode" -eq 0 ]; then
    echo "Error: not inside a git work tree (use --all to run tmux-only pruning)." >&2
    exit 1
  fi
fi

if ! command -v tmux >/dev/null 2>&1; then
  exit 0
fi

session_has_any_existing_pane_path() {
  local session_name="$1"
  local pane_path
  local saw_any=0

  while IFS= read -r pane_path; do
    [ -z "$pane_path" ] && continue
    saw_any=1
    if [ -e "$pane_path" ]; then
      return 0
    fi
  done < <(tmux list-panes -t "$session_name" -F '#{pane_current_path}' 2>/dev/null || true)

  if [ "$saw_any" -eq 0 ]; then
    return 0
  fi

  return 1
}

stale_sessions=()
while IFS=$'\t' read -r session_name _; do
  [ -z "$session_name" ] && continue

  if [ "$all_mode" -eq 0 ]; then
    case "$session_name" in
    "${parent_name}"\|*) ;;
    *)
      continue
      ;;
    esac
  fi

  if ! session_has_any_existing_pane_path "$session_name"; then
    stale_sessions+=("$session_name")
  fi
done < <(tmux list-sessions -F $'#{session_name}\t#{session_path}' 2>/dev/null || true)

if [ ${#stale_sessions[@]} -gt 0 ]; then
  tmux_has_stale=1
fi

if [ "$apply_mode" -eq 0 ]; then
  printed_any=0
  if [ "$git_has_stale" -eq 1 ] && [ "$quiet_mode" -eq 0 ]; then
    echo "Stale git worktree metadata:"
    echo "$dry_run_output"
    printed_any=1
  fi

  if [ "$tmux_has_stale" -eq 1 ]; then
    if [ "$quiet_mode" -eq 0 ]; then
      if [ "$printed_any" -eq 1 ]; then
        echo
      fi
      if [ "$all_mode" -eq 1 ]; then
        echo "Stale tmux sessions (no existing pane paths; use --apply to kill):"
      else
        echo "Stale ,w tmux sessions for '$parent_name' (no existing pane paths; use --apply to kill):"
      fi
      printf '  %s\n' "${stale_sessions[@]}"
    fi
    exit 0
  fi

  if [ "$quiet_mode" -eq 0 ]; then
    if [ "$printed_any" -eq 0 ]; then
      echo "Nothing to prune."
    fi
  fi
  exit 0
fi

did_any=0
if [ "$git_has_stale" -eq 1 ]; then
  git worktree prune 2>&1 || true
  did_any=1
fi

if [ "$tmux_has_stale" -eq 1 ]; then
  for session_name in "${stale_sessions[@]}"; do
    tmux kill-session -t "$session_name" 2>/dev/null || true
  done
  did_any=1
fi

if [ "$quiet_mode" -eq 0 ] && [ "$did_any" -eq 0 ]; then
  echo "Nothing to prune."
fi

exit 0
