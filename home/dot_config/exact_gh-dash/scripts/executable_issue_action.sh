#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: issue_action.sh <action> <repo_name> <repo_path> <issue_number>

Actions:
  focus             Create/switch issue worktree and focus tmux session (quiet).
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
  cd "$p" 2>/dev/null || return 1

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
    common="$(git -C "$child" rev-parse --git-common-dir 2>/dev/null || true)"
    [ -n "$common" ] || continue
    case "$common" in
    /*) ;;
    *) common="$child/$common" ;;
    esac
    common="$(realpath "$common" 2>/dev/null || printf '%s' "$common")"
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
      "env OUTER_TMUX_SOCKET=\"${OUTER_TMUX_SOCKET}\" OUTER_TMUX_CLIENT=\"${OUTER_TMUX_CLIENT:-}\" bash -lc ',gh-tfork \"$repo_name\" || { echo; echo \"Bootstrap failed. Press any key to close.\"; read -n 1; exit 1; }'" ||
      die "failed to initialize missing repo via ,gh-tfork: $repo_name"
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

  if wt="$(resolve_repo_worktree "$repo_path" 2>/dev/null)"; then
    printf '%s\n' "$wt"
    return 0
  fi

  conventional_repo_path="$(_conventional_repo_wrapper_path "$repo_name")"
  if [ "$conventional_repo_path" != "$(expand_tilde "$repo_path")" ] &&
    wt="$(resolve_repo_worktree "$conventional_repo_path" 2>/dev/null)"; then
    printf '%s\n' "$wt"
    return 0
  fi

  bootstrap_repo_with_tfork "$repo_name" "$show_progress_popup"

  wt="$(resolve_repo_worktree "$conventional_repo_path" 2>/dev/null || true)"
  if [ -z "$wt" ]; then
    wt="$(resolve_repo_worktree "$repo_path" 2>/dev/null || true)"
  fi
  [ -n "$wt" ] || die "could not find a git worktree under: $(expand_tilde "$conventional_repo_path")"
  printf '%s\n' "$wt"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

action="${1:-}"
repo_name="${2:-}"

# If repo_path is empty but issue_number is provided, shift them
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

# Ensure chezmoi-installed commands are available.
PATH="$HOME/bin:$PATH"
bootstrap_progress_mode=0
case "$action" in
focus)
  bootstrap_progress_mode=1
  ;;
*)
  usage >&2
  exit 1
  ;;
esac

wt="$(ensure_repo_worktree "$repo_name" "$repo_path" "$bootstrap_progress_mode")"

case "$action" in
focus)
  cd "$wt"
  require_cmd gh
  require_cmd ,w
  if [ "${GH_DASH_POPUP:-0}" = "1" ] && [ -n "${OUTER_TMUX_SOCKET:-}" ]; then
    tmux display-popup -E -w 80% -h 80% -d "$wt" -T " Worktree: Issue #$issue_number " \
      "env OUTER_TMUX_SOCKET=\"${OUTER_TMUX_SOCKET}\" OUTER_TMUX_CLIENT=\"${OUTER_TMUX_CLIENT:-}\" bash -lc ',w issue --focus \"$issue_number\" || { echo; echo \"Failed. Press any key to close.\"; read -n 1; }'"
  else
    ,w issue -q --focus "$issue_number"
  fi
  ;;
esac
