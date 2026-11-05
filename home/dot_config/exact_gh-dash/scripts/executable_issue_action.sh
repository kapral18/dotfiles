#!/usr/bin/env bash
set -euo pipefail

PATH="$HOME/bin:$PATH"

usage() {
  cat << 'EOF'
Usage: issue_action.sh <action> <repo_name> <repo_path> <issue_number>

Actions:
  focus             Create/switch issue worktree and focus its herdr workspace (quiet).
EOF
}

die() {
  echo "gh-dash: $*" >&2
  exit 1
}

run_issue_focus() {
  local repo_name="$1"
  local repo_path="$2"
  local issue_number="$3"

  local -a args
  args=(issue "$repo_name" "$issue_number" --focus --quiet)
  if [ -n "$repo_path" ]; then
    args+=(--repo-path "$repo_path")
  fi
  ,gh-worktree "${args[@]}"
}

action="${1:-}"
repo_name="${2:-}"

# If repo_path is empty but issue_number is provided, shift them.
if [ $# -eq 3 ] && [[ "$3" =~ ^[0-9]+$ ]]; then
  repo_path=""
  issue_number="$3"
else
  repo_path="${3:-}"
  issue_number="${4:-}"
fi

if [ -z "$action" ] || [ -z "$repo_name" ] || [ -z "$issue_number" ]; then
  usage >&2
  exit 1
fi

case "$issue_number" in
  *[!0-9]* | "") die "invalid issue number: $issue_number" ;;
esac

case "$action" in
  focus)
    run_issue_focus "$repo_name" "$repo_path" "$issue_number"
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
