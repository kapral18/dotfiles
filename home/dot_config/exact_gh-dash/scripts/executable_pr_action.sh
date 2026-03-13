#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat << 'EOF'
Usage: pr_action.sh <action> <repo_name> <repo_path> <pr_number>

Actions:
  focus            Create/switch PR worktree and focus tmux session (quiet).
  create_bg         Create PR worktree in background (quiet, logs to cache).
  octo_review       Create/switch PR worktree, focus tmux, then open Octo review in new tmux window.
EOF
}

die() {
  echo "gh-dash: $*" >&2
  exit 1
}

expand_tilde() {
  local p="$1"
  case "$p" in
    "~") printf '%s\n' "$HOME" ;;
    "~/"*) printf '%s\n' "$HOME/${p#~/}" ;;
    *) printf '%s\n' "$p" ;;
  esac
}

resolve_repo_worktree() {
  local p="$1"
  local d child_git child common root
  p="$(expand_tilde "$p")"
  cd "$p" 2> /dev/null || return 1

  if [ -e ".git" ]; then
    pwd -P
    return 0
  fi

  local d
  for d in main master dev develop trunk; do
    if [ -e "$d/.git" ]; then
      cd "$d"
      pwd -P
      return 0
    fi
  done

  # Fallback: discover root checkout from any child worktree, including
  # default branch names outside the standard main/master/dev set.
  for child_git in "$p"/*/.git "$p"/*/*/.git "$p"/*/*/*/.git; do
    [ -e "$child_git" ] || continue
    child="$(dirname "$child_git")"
    common="$(git -C "$child" rev-parse --git-common-dir 2> /dev/null || true)"
    [ -n "$common" ] || continue
    case "$common" in
      /*) ;;
      *) common="$child/$common" ;;
    esac
    common="$(realpath "$common" 2> /dev/null || printf '%s' "$common")"
    if [ "$(basename "$common")" = ".git" ]; then
      root="$(dirname "$common")"
      if [ -e "$root/.git" ]; then
        printf '%s\n' "$root"
        return 0
      fi
    fi
  done

  return 1
}

bootstrap_repo_with_tfork() {
  local repo_name="$1"
  local show_progress_popup="${2:-0}"
  local parent_path

  require_cmd ,gh-tfork
  parent_path="$(_conventional_parent_for_repo "$repo_name")"
  mkdir -p "$parent_path"

  if [ "$show_progress_popup" = "1" ] && [ "${GH_DASH_POPUP:-0}" = "1" ] && [ -n "${OUTER_TMUX_SOCKET:-}" ]; then
    tmux display-popup -E -w 80% -h 80% -d "$parent_path" -T " Bootstrap: $repo_name " \
      "env OUTER_TMUX_SOCKET=\"${OUTER_TMUX_SOCKET}\" OUTER_TMUX_CLIENT=\"${OUTER_TMUX_CLIENT:-}\" bash -lc ',gh-tfork \"$repo_name\" || { echo; echo \"Bootstrap failed. Press any key to close.\"; read -n 1; exit 1; }'" \
      || die "failed to initialize missing repo via ,gh-tfork: $repo_name"
    return 0
  fi

  (
    cd "$parent_path"
    ,gh-tfork "$repo_name"
  ) || die "failed to initialize missing repo via ,gh-tfork: $repo_name"
}

_conventional_parent_for_repo() {
  local repo_name="$1"
  local owner="${repo_name%%/*}"
  if [ "$owner" = "elastic" ]; then
    printf '%s\n' "$HOME/work"
  else
    printf '%s\n' "$HOME/code"
  fi
}

_conventional_repo_wrapper_path() {
  local repo_name="$1"
  local parent_path repo
  parent_path="$(_conventional_parent_for_repo "$repo_name")"
  repo="${repo_name##*/}"
  printf '%s\n' "${parent_path}/${repo}"
}

ensure_repo_worktree() {
  local repo_name="$1"
  local repo_path="$2"
  local show_progress_popup="${3:-0}"
  local wt="" conventional_repo_path=""

  if wt="$(resolve_repo_worktree "$repo_path" 2> /dev/null)"; then
    printf '%s\n' "$wt"
    return 0
  fi

  conventional_repo_path="$(_conventional_repo_wrapper_path "$repo_name")"
  if [ "$conventional_repo_path" != "$(expand_tilde "$repo_path")" ] \
    && wt="$(resolve_repo_worktree "$conventional_repo_path" 2> /dev/null)"; then
    printf '%s\n' "$wt"
    return 0
  fi

  bootstrap_repo_with_tfork "$repo_name" "$show_progress_popup"

  wt="$(resolve_repo_worktree "$conventional_repo_path" 2> /dev/null || true)"
  if [ -z "$wt" ]; then
    wt="$(resolve_repo_worktree "$repo_path" 2> /dev/null || true)"
  fi
  [ -n "$wt" ] || die "could not find a git worktree under: $(expand_tilde "$conventional_repo_path")"
  printf '%s\n' "$wt"
}

require_tmux() {
  [ -n "${TMUX:-}" ] || die "TMUX is empty (this action expects tmux)"
  command -v tmux > /dev/null 2>&1 || die "missing command: tmux"
}

require_cmd() {
  command -v "$1" > /dev/null 2>&1 || die "missing command: $1"
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

run_focus_in_popup() {
  local pr_number="$1"
  if ! ,w prs --focus "$pr_number"; then
    echo
    echo "Failed. Press any key to close."
    read -r -n 1
    return 1
  fi
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

action="${1:-}"
repo_name="${2:-}"

# If repo_path is empty but pr_number is provided, shift them
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

# Ensure chezmoi-installed commands are available.
PATH="$HOME/bin:$PATH"
bootstrap_progress_mode=0
case "$action" in
  focus | octo_review)
    bootstrap_progress_mode=1
    ;;
esac

wt="$(ensure_repo_worktree "$repo_name" "$repo_path" "$bootstrap_progress_mode")"

case "$action" in
  focus)
    cd "$wt"
    require_cmd gh
    require_cmd ,w
    if [ "${GH_DASH_POPUP:-0}" = "1" ] && [ -n "${OUTER_TMUX_SOCKET:-}" ]; then
      popup_run_self "$wt" " Worktree: PR #$pr_number " __popup_focus "$repo_name" "$repo_path" "$pr_number"
    else
      ,w prs -q --focus "$pr_number"
    fi
    ;;

  create_bg)
    cd "$wt"
    require_cmd gh
    require_cmd ,w
    log_dir="${XDG_CACHE_HOME:-$HOME/.cache}/gh-dash"
    mkdir -p "$log_dir"
    log="${log_dir}/w_prs_${pr_number}.log"
    nohup ,w prs -q "$pr_number" > "$log" 2>&1 &
    ;;

  octo_review)
    cd "$wt"
    require_tmux
    require_cmd gh
    require_cmd ,w
    require_cmd nvim

    if [ "${GH_DASH_POPUP:-0}" = "1" ] && [ -n "${OUTER_TMUX_SOCKET:-}" ]; then
      popup_run_self "$wt" " Worktree: PR #$pr_number " __popup_octo_review "$repo_name" "$repo_path" "$pr_number"
    else
      ,w prs -q --focus "$pr_number"
      open_octo_review_window "$wt" "$pr_number" "$repo_name"
    fi
    ;;

  __popup_focus)
    cd "$wt"
    require_cmd gh
    require_cmd ,w
    run_focus_in_popup "$pr_number"
    ;;

  __popup_octo_review)
    cd "$wt"
    require_tmux
    require_cmd gh
    require_cmd ,w
    require_cmd nvim
    run_focus_in_popup "$pr_number"
    open_octo_review_window "$wt" "$pr_number" "$repo_name"
    ;;

  *)
    usage >&2
    exit 1
    ;;
esac
