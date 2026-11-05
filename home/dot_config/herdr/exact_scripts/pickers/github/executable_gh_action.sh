#!/usr/bin/env bash
# Action handler for the GitHub picker.
# Delegates repo bootstrap + worktree creation to ,gh-worktree.
#
# Usage: gh_action.sh <action> <kind> <repo_nwo> <number> <url>
#
# Actions:
#   checkout   Create worktree + focus its herdr workspace
#   open       Open in browser
#   octo       Create worktree + focus + open Octo review
set -euo pipefail
# shellcheck source=../lib/herdr_ws.sh
. "$HOME/.config/herdr/scripts/pickers/lib/herdr_ws.sh"

PATH="$HOME/bin:$PATH"

die() {
  printf 'gh_action: %s\n' "$*" >&2
  exit 1
}

show_loader() {
  local message="$1"
  if [ -n "${HERDR_SOCKET_PATH:-}" ]; then
    picker_notify "gh-picker: Loading... ${message}"
  fi
  if [ -t 2 ]; then
    printf '\033[2;38;5;244m  Loading... %s\033[0m\n' "$message" >&2
  fi
}

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/herdr-pickers"

_mark_local_in_cache() {
  local k="$1" repo="$2" num="$3"
  local cache_file patcher
  cache_file="${cache_dir}/gh_picker.tsv"
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
        show_loader "checking out ${repo_nwo}#${number}"
        if ,gh-worktree pr "$repo_nwo" "$number" --focus; then
          _mark_local_in_cache "pr" "$repo_nwo" "$number"
        elif [ -n "$url" ]; then
          open "$url" 2> /dev/null || xdg-open "$url" 2> /dev/null || true
        fi
        ;;
      issue)
        show_loader "checking out ${repo_nwo}#${number}"
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
        nvim_cmd="nvim ${wt_cwd}/.git \"+silent! sleep 200m | Octo pr edit $number $repo_nwo\""
        # ,gh-worktree --focus just focused the worktree's workspace; open the tab there.
        wt_ws="$(herdr workspace list | jq -r 'first(.result.workspaces[] | select(.focused) | .workspace_id) // empty')"
        if [ -n "$wt_ws" ]; then
          octo_pane="$(herdr tab create --workspace "$wt_ws" --cwd "$wt_cwd" --label "octo#${number}" --focus | jq -r '.result.root_pane.pane_id')"
          herdr pane run "$octo_pane" "$nvim_cmd" > /dev/null
        fi
      fi
    fi
    ;;
  *)
    die "unknown action: $action"
    ;;
esac
