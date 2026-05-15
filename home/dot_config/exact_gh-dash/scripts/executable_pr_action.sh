#!/usr/bin/env bash
set -euo pipefail

PATH="$HOME/bin:$PATH"

usage() {
  cat << 'EOF'
Usage: pr_action.sh <action> <repo_name> <repo_path> <pr_number>

Actions:
  focus            Create/switch PR worktree and focus tmux session (quiet).
  create_bg        Create PR worktree in background (quiet, logs to cache).
  octo_review      Create/switch PR worktree, focus tmux, then open Octo review in new tmux window.
EOF
}

die() {
  echo "gh-dash: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" > /dev/null 2>&1 || die "missing command: $1"
}

require_tmux() {
  if [ -z "${TMUX:-}" ] && [ -z "${OUTER_TMUX_SOCKET:-}" ]; then
    die "TMUX is empty (this action expects tmux)"
  fi
  require_cmd tmux
}

outer_tmux() {
  if [ -n "${OUTER_TMUX_SOCKET:-}" ]; then
    tmux -S "${OUTER_TMUX_SOCKET}" "$@"
    return $?
  fi
  tmux "$@"
}

outer_tmux_fmt_for_client() {
  local fmt="$1"
  if [ -n "${OUTER_TMUX_SOCKET:-}" ] && [ -n "${OUTER_TMUX_CLIENT:-}" ]; then
    outer_tmux display-message -p -c "${OUTER_TMUX_CLIENT}" -F "${fmt}" 2> /dev/null || true
    return 0
  fi
  outer_tmux display-message -p -F "${fmt}" 2> /dev/null || true
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
  shift 2

  local cmd
  cmd="$(shell_join_quoted env \
    OUTER_TMUX_SOCKET="${OUTER_TMUX_SOCKET:-}" \
    OUTER_TMUX_CLIENT="${OUTER_TMUX_CLIENT:-}" \
    bash "$0" "$@")"

  tmux display-popup -E -w 80% -h 80% -d "$start_dir" -T "$title" "$cmd"
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

open_octo_review_window() {
  local review_cwd="$1"
  local pr_number="$2"
  local repo_name="$3"
  local target_session nvim_cmd

  target_session="$(outer_tmux_fmt_for_client '#{session_name}')"
  nvim_cmd="$(shell_join_quoted \
    nvim "$review_cwd/.git" \
    "+silent! sleep 200m | Octo pr edit ${pr_number} ${repo_name}")"

  if [ -n "$target_session" ]; then
    outer_tmux new-window -t "${target_session}:" -c "$review_cwd" -n "octo#${pr_number}" "$nvim_cmd"
  else
    outer_tmux new-window -c "$review_cwd" -n "octo#${pr_number}" "$nvim_cmd"
  fi
}

run_focus_in_popup() {
  local repo_name="$1"
  local repo_path="$2"
  local pr_number="$3"
  if ! gh_worktree_pr focus "$repo_name" "$repo_path" "$pr_number"; then
    echo
    echo "Failed. Press any key to close."
    read -r -n 1
    return 1
  fi
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
    if [ "${GH_DASH_POPUP:-0}" = "1" ] && [ -n "${OUTER_TMUX_SOCKET:-}" ]; then
      popup_run_self "$HOME" " Worktree: PR #$pr_number " __popup_focus "$repo_name" "$repo_path" "$pr_number"
    else
      gh_worktree_pr focus "$repo_name" "$repo_path" "$pr_number"
    fi
    ;;

  create_bg)
    gh_worktree_pr create_bg "$repo_name" "$repo_path" "$pr_number"
    ;;

  octo_review)
    require_cmd nvim
    require_tmux
    if [ "${GH_DASH_POPUP:-0}" = "1" ] && [ -n "${OUTER_TMUX_SOCKET:-}" ]; then
      popup_run_self "$HOME" " Worktree: PR #$pr_number " __popup_octo_review "$repo_name" "$repo_path" "$pr_number"
    else
      gh_worktree_pr focus "$repo_name" "$repo_path" "$pr_number"
      review_cwd="$(gh_worktree_pr print_root "$repo_name" "$repo_path" "$pr_number" 2> /dev/null || true)"
      [ -n "$review_cwd" ] || review_cwd="$HOME"
      open_octo_review_window "$review_cwd" "$pr_number" "$repo_name"
    fi
    ;;

  __popup_focus)
    run_focus_in_popup "$repo_name" "$repo_path" "$pr_number"
    ;;

  __popup_octo_review)
    require_cmd nvim
    require_tmux
    run_focus_in_popup "$repo_name" "$repo_path" "$pr_number"
    review_cwd="$(gh_worktree_pr print_root "$repo_name" "$repo_path" "$pr_number" 2> /dev/null || true)"
    [ -n "$review_cwd" ] || review_cwd="$HOME"
    open_octo_review_window "$review_cwd" "$pr_number" "$repo_name"
    ;;

  *)
    usage >&2
    exit 1
    ;;
esac
