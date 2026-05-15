#!/usr/bin/env bash
# Action handler for the GitHub picker.
# Delegates repo bootstrap + worktree creation to ,gh-worktree.
#
# Usage: gh_action.sh <action> <kind> <repo_nwo> <number> <url>
#
# Actions:
#   checkout   Create worktree + focus tmux session
#   open       Open in browser
#   octo       Create worktree + focus + open Octo review
set -euo pipefail

PATH="$HOME/bin:$PATH"

die() {
  printf 'gh_action: %s\n' "$*" >&2
  exit 1
}

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"

_mark_local_in_cache() {
  local k="$1" repo="$2" num="$3"
  local mode cache_file patcher
  mode="$(cat "${cache_dir}/gh_picker_mode" 2> /dev/null || echo work)"
  cache_file="${cache_dir}/gh_picker_${mode}.tsv"
  patcher="$(cd "$(dirname "$0")" && pwd)/lib/gh_patch_picker_cache.py"
  if [ -f "$patcher" ] && [ -f "$cache_file" ]; then
    python3 -u "$patcher" --cache-file "$cache_file" --kind "$k" --repo "$repo" --num "$num" 2> /dev/null || true
  fi
}

action="${1:-}"
kind="${2:-}"
repo_nwo="${3:-}"
number="${4:-}"
url="${5:-}"

[ -n "$action" ] || die "missing action"
[ -n "$kind" ] || die "missing kind"
[ -n "$repo_nwo" ] || die "missing repo"
[ -n "$number" ] || die "missing number"

case "$action" in
  open)
    if [ -n "$url" ]; then
      open "$url" 2> /dev/null || xdg-open "$url" 2> /dev/null || true
    fi
    exit 0
    ;;
  checkout | octo)
    case "$kind" in
      pr)
        if ,gh-worktree pr "$repo_nwo" "$number" --focus; then
          _mark_local_in_cache "pr" "$repo_nwo" "$number"
        elif [ -n "$url" ]; then
          open "$url" 2> /dev/null || xdg-open "$url" 2> /dev/null || true
        fi
        ;;
      issue)
        ,gh-worktree issue "$repo_nwo" "$number" --focus
        _mark_local_in_cache "issue" "$repo_nwo" "$number"
        ;;
      *)
        die "unknown kind: $kind"
        ;;
    esac

    if [ "$action" = "octo" ] && [ "$kind" = "pr" ]; then
      if command -v nvim > /dev/null 2>&1; then
        wt_cwd="$(,gh-worktree pr "$repo_nwo" "$number" --print-root 2> /dev/null || true)"
        [ -n "$wt_cwd" ] || wt_cwd="$HOME"
        target_session="$(tmux display-message -p '#{client_session}' 2> /dev/null || true)"
        [ -n "$target_session" ] || target_session="$(tmux display-message -p '#{session_name}' 2> /dev/null || true)"
        fish_shell="${SHELL:-$(command -v fish 2> /dev/null || echo /bin/sh)}"
        nvim_cmd="nvim ${wt_cwd}/.git \"+silent! sleep 200m | Octo pr edit $number $repo_nwo\""
        if [ -n "$target_session" ]; then
          tmux new-window -t "${target_session}:" -c "$wt_cwd" -n "octo#${number}" -e "SHELL=$fish_shell" "$fish_shell" -c "$nvim_cmd"
        fi
      fi
    fi
    ;;
  *)
    die "unknown action: $action"
    ;;
esac
