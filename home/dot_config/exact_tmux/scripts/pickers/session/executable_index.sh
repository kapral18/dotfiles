#!/usr/bin/env bash
# Re-exec under a modern bash when macOS ships bash 3.2 as /bin/bash.
if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
  _b="$(brew --prefix bash 2> /dev/null)/bin/bash"
  [ -x "$_b" ] && exec "$_b" "$0" "$@"
  exit 1
fi
set -euo pipefail

need_cmd() {
  local cmd="$1"
  command -v "${cmd}" > /dev/null 2>&1
}

tmux_opt() {
  local key="$1"
  local default_value="$2"
  local value=""
  value="$(tmux show-option -gqv "${key}" 2> /dev/null || true)"
  if [ -n "$value" ]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$default_value"
  fi
}

DIR_ICON_COLORED=$'\033[38;5;75m\033[0m'
DIR_PATH_COLOR_PREFIX=$'\033[38;5;110m'
ANSI_RESET=$'\033[0m'
DEFAULT_PICK_SESSION_DIR_EXCLUDE_FILE="$HOME/.config/tmux/pick_session_dir_exclude.txt"

normalize_path_opt() {
  local p="${1:-}"
  case "$p" in
    "~") printf '%s\n' "$HOME" ;;
    "~/"*) printf '%s\n' "$HOME/${p#"~/"}" ;;
    *) printf '%s\n' "$p" ;;
  esac
}

pick_session_ignore_file() {
  local file_opt
  file_opt="$(tmux_opt '@pick_session_dir_exclude_file' "$DEFAULT_PICK_SESSION_DIR_EXCLUDE_FILE")"
  file_opt="$(normalize_path_opt "$file_opt")"
  [ -f "$file_opt" ] && printf '%s\n' "$file_opt"
}

tildefy_to_reply() {
  local p="$1"
  # shellcheck disable=SC2034,SC2088
  case "$p" in
    "$HOME") REPLY="~" ;;
    "$HOME"/*) REPLY="~/${p#"$HOME"/}" ;;
    *) REPLY="$p" ;;
  esac
}

print_dir_row() {
  local path="$1"
  tildefy_to_reply "$path"
  local base="${path##*/}"
  [ -n "$base" ] || base="$path"
  local mk
  mk="${base} ${REPLY} ${path}"
  printf '%s  %s%s%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${DIR_ICON_COLORED}" "$DIR_PATH_COLOR_PREFIX" "$REPLY" "$ANSI_RESET" \
    "dir" "$path" "" "" "${base} ${REPLY} ${path}"
}

is_git_repo() {
  git rev-parse --is-inside-work-tree > /dev/null 2>&1
}

emit_sessions_worktrees_and_dirs() {
  need_cmd tmux || return 0

  export PICK_SESSION_SCAN_ROOTS
  export PICK_SESSION_SCAN_DEPTH
  export PICK_SESSION_QUICK
  export PICK_SESSION_SESSIONS_ONLY
  export PICK_SESSION_IGNORE_FILE
  export PICK_SESSION_DIR_INCLUDE_HIDDEN
  export PICK_SESSION_GITHUB_LOGIN
  export PICK_SESSION_THREADS

  PICK_SESSION_SCAN_ROOTS="$(tmux_opt '@pick_session_worktree_scan_roots' "$HOME/work,$HOME/code,$HOME/.backport/repositories,$HOME/.local/share")"
  PICK_SESSION_SCAN_DEPTH="$(tmux_opt '@pick_session_worktree_scan_depth' '6')"
  PICK_SESSION_IGNORE_FILE="$(pick_session_ignore_file)"
  PICK_SESSION_QUICK="$quick_mode"
  PICK_SESSION_SESSIONS_ONLY="$sessions_only"
  PICK_SESSION_DIR_INCLUDE_HIDDEN="$(tmux_opt '@pick_session_dir_include_hidden' 'on')"
  PICK_SESSION_GITHUB_LOGIN="$(tmux_opt '@pick_session_github_login' '')"

  python3 -u "$(cd "$(dirname "$0")" && pwd)/lib/index_main.py"
}

quick_mode=0
sessions_only=0
while [ $# -gt 0 ]; do
  case "$1" in
    --quick) quick_mode=1 ;;
    --sessions-only) sessions_only=1 ;;
  esac
  shift
done

emit_sessions_worktrees_and_dirs
