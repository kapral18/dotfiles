#!/usr/bin/env bash
set -euo pipefail

PATH="$HOME/bin:$PATH"

usage() {
  cat << 'EOF'
Usage: issue_action.sh <action> <repo_name> <repo_path> <issue_number>

Actions:
  focus             Create/switch issue worktree and focus tmux session (quiet).
EOF
}

die() {
  echo "gh-dash: $*" >&2
  exit 1
}

shell_join_quoted() {
  local out="" arg
  for arg in "$@"; do
    out+="$(printf '%q' "$arg") "
  done
  printf '%s' "${out% }"
}

popup_run_self() {
  local start_dir="$1"
  local title="$2"
  local repo_name="$3"
  local repo_path="$4"
  local issue_number="$5"

  local cmd
  cmd="$(shell_join_quoted env \
    OUTER_TMUX_SOCKET="${OUTER_TMUX_SOCKET:-}" \
    OUTER_TMUX_CLIENT="${OUTER_TMUX_CLIENT:-}" \
    bash "$0" __popup_focus "$repo_name" "$repo_path" "$issue_number")"

  tmux display-popup -E -w 80% -h 80% -d "$start_dir" -T "$title" "$cmd"
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
    if [ "${GH_DASH_POPUP:-0}" = "1" ] && [ -n "${OUTER_TMUX_SOCKET:-}" ]; then
      popup_run_self "$HOME" " Worktree: Issue #$issue_number " "$repo_name" "$repo_path" "$issue_number"
    else
      run_issue_focus "$repo_name" "$repo_path" "$issue_number"
    fi
    ;;
  __popup_focus)
    if ! run_issue_focus "$repo_name" "$repo_path" "$issue_number"; then
      echo
      echo "Failed. Press any key to close."
      read -r -n 1
      exit 1
    fi
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
