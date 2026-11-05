#!/usr/bin/env bash
set -euo pipefail

PATH="$HOME/bin:$PATH"

usage() {
  cat << 'EOF'
Usage: pr_action.sh <action> <repo_name> <repo_path> <pr_number>

Actions:
  focus            Create/switch PR worktree and focus its herdr workspace (quiet).
  create_bg        Create PR worktree in background (quiet, logs to cache).
  octo_review      Create/switch PR worktree, focus it, then open the Octo review in a new herdr tab.
EOF
}

die() {
  echo "gh-dash: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" > /dev/null 2>&1 || die "missing command: $1"
}

shell_join_quoted() {
  local out="" arg
  for arg in "$@"; do
    out+="$(printf '%q' "$arg") "
  done
  printf '%s' "${out% }"
}

gh_worktree_pr() {
  local mode="$1"
  local repo_name="$2"
  local repo_path="$3"
  local pr_number="$4"

  local -a args
  args=(pr "$repo_name" "$pr_number" --quiet)
  if [ -n "$repo_path" ]; then
    args+=(--repo-path "$repo_path")
  fi

  case "$mode" in
    focus) args+=(--focus) ;;
    create_bg) args+=(--create-bg) ;;
    print_root) args+=(--print-root) ;;
    *) die "unsupported gh_worktree_pr mode: $mode" ;;
  esac

  ,gh-worktree "${args[@]}"
}

open_octo_review_tab() {
  local review_cwd="$1"
  local pr_number="$2"
  local repo_name="$3"
  local ws_id pane

  # gh_worktree_pr focus just focused the worktree's workspace; open the tab there.
  ws_id="$(herdr workspace list | jq -r 'first(.result.workspaces[] | select(.focused) | .workspace_id) // empty')"
  [ -n "$ws_id" ] || die "no focused herdr workspace"
  pane="$(herdr tab create --workspace "$ws_id" --cwd "$review_cwd" --label "octo#${pr_number}" --focus | jq -r '.result.root_pane.pane_id')"
  herdr pane run "$pane" "$(shell_join_quoted nvim "$review_cwd/.git" "+silent! sleep 200m | Octo pr edit ${pr_number} ${repo_name}")" > /dev/null
}

action="${1:-}"
repo_name="${2:-}"

# If repo_path is empty but pr_number is provided, shift them.
if [ $# -eq 3 ] && [[ "$3" =~ ^[0-9]+$ ]]; then
  repo_path=""
  pr_number="$3"
else
  repo_path="${3:-}"
  pr_number="${4:-}"
fi

if [ -z "$action" ] || [ -z "$repo_name" ] || [ -z "$pr_number" ]; then
  usage >&2
  exit 1
fi

case "$pr_number" in
  *[!0-9]* | "") die "invalid pr number: $pr_number" ;;
esac

case "$action" in
  focus)
    gh_worktree_pr focus "$repo_name" "$repo_path" "$pr_number"
    ;;

  create_bg)
    gh_worktree_pr create_bg "$repo_name" "$repo_path" "$pr_number"
    ;;

  octo_review)
    require_cmd nvim
    require_cmd herdr
    gh_worktree_pr focus "$repo_name" "$repo_path" "$pr_number"
    review_cwd="$(gh_worktree_pr print_root "$repo_name" "$repo_path" "$pr_number" 2> /dev/null || true)"
    [ -n "$review_cwd" ] || review_cwd="$HOME"
    open_octo_review_tab "$review_cwd" "$pr_number" "$repo_name"
    ;;

  *)
    usage >&2
    exit 1
    ;;
esac
