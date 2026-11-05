#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$script_dir/../shared/bash_utils_lib.sh"
source "$script_dir/../shared/worktree_lib.sh"

show_usage() {
  cat << EOF
Usage: ,w prune [-q|--quiet] [--apply] [--all]

Prune stale worktree metadata and (optionally) close stale herdr workspaces.

Options:
  -q, --quiet       Suppress informational output
  --apply           Apply changes (default is dry-run output only)
  --all             Consider herdr workspaces across all repos (not just this repo's ,w workspaces)
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
if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
  in_git_repo=1
fi

parent_name=""
if [ "$in_git_repo" -eq 1 ]; then
  parent_dir=$(_get_worktree_parent_dir)
  parent_name="$(_comma_w_parent_name_from_dir "$parent_dir")"
  session_prefix="$(_comma_w_workspace_name "$parent_name" "")"
  session_prefix="${session_prefix%|}"
fi

git_has_stale=0
ws_has_stale=0

if [ "$in_git_repo" -eq 1 ]; then
  dry_run_output="$(git worktree prune --dry-run 2>&1 || true)"
  if [ -n "${dry_run_output//[[:space:]]/}" ]; then
    git_has_stale=1
  fi
else
  if [ "$all_mode" -eq 0 ]; then
    echo "Error: not inside a git work tree (use --all to run workspace-only pruning)." >&2
    exit 1
  fi
fi

stale_ids=()
stale_sessions=()
if command -v herdr > /dev/null 2>&1; then
  prune_prefix=""
  [ "$all_mode" -eq 1 ] || prune_prefix="$session_prefix"
  while IFS=$'\t' read -r ws_id ws_label; do
    [ -n "$ws_id" ] || continue
    stale_ids+=("$ws_id")
    stale_sessions+=("$ws_label")
  done < <(_comma_w_stale_workspaces "$prune_prefix")
fi

if [ ${#stale_sessions[@]} -gt 0 ]; then
  ws_has_stale=1
fi

if [ "$apply_mode" -eq 0 ]; then
  printed_any=0
  if [ "$git_has_stale" -eq 1 ] && [ "$quiet_mode" -eq 0 ]; then
    echo "Stale git worktree metadata:"
    echo "$dry_run_output"
    printed_any=1
  fi

  if [ "$ws_has_stale" -eq 1 ]; then
    if [ "$quiet_mode" -eq 0 ]; then
      if [ "$printed_any" -eq 1 ]; then
        echo
      fi
      if [ "$all_mode" -eq 1 ]; then
        echo "Stale herdr workspaces (no existing pane paths; use --apply to close):"
      else
        echo "Stale ,w workspaces for '$parent_name' (no existing pane paths; use --apply to close):"
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

if [ "$ws_has_stale" -eq 1 ]; then
  for ws_id in "${stale_ids[@]+"${stale_ids[@]}"}"; do
    _comma_w_herdr workspace close "$ws_id" > /dev/null 2>&1 || true
  done
  did_any=1
fi

if [ "$quiet_mode" -eq 0 ] && [ "$did_any" -eq 0 ]; then
  echo "Nothing to prune."
fi

exit 0
