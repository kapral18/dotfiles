#!/usr/bin/env bash
# Action handler for the GitHub picker.
# Resolves the local repo path and delegates to ,w for worktree creation.
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

expand_tilde() {
  local p="$1"
  case "$p" in
    "~") printf '%s\n' "$HOME" ;;
    "~/"*) printf '%s\n' "$HOME/${p#~/}" ;;
    *) printf '%s\n' "$p" ;;
  esac
}

resolve_repo_path() {
  local nwo="$1"
  local owner="${nwo%%/*}"
  local repo="${nwo#*/}"

  local parent=""
  if [ "$owner" = "elastic" ]; then
    parent="$HOME/work"
  else
    parent="$HOME/code"
  fi

  local wrapper="$parent/$repo"
  if [ -d "$wrapper" ]; then
    for d in main master dev develop trunk; do
      if [ -e "$wrapper/$d/.git" ]; then
        printf '%s\n' "$wrapper/$d"
        return 0
      fi
    done
    if [ -e "$wrapper/.git" ]; then
      printf '%s\n' "$wrapper"
      return 0
    fi
    # Check any child that has .git
    local child_git
    for child_git in "$wrapper"/*/.git; do
      [ -e "$child_git" ] || continue
      printf '%s\n' "$(dirname "$child_git")"
      return 0
    done
  fi

  printf '%s\n' "$wrapper"
}

bootstrap_repo() {
  local nwo="$1"
  local owner="${nwo%%/*}"
  local parent=""
  if [ "$owner" = "elastic" ]; then
    parent="$HOME/work"
  else
    parent="$HOME/code"
  fi
  mkdir -p "$parent"

  if command -v ,gh-tfork > /dev/null 2>&1; then
    (cd "$parent" && ,gh-tfork "$nwo") || die "failed to bootstrap $nwo via ,gh-tfork"
  else
    die "repo $nwo not found locally and ,gh-tfork not available"
  fi
}

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"

_mark_local_in_cache() {
  local k="$1" repo="$2" num="$3"
  local mode cache_file patcher
  mode="$(cat "${cache_dir}/gh_picker_mode" 2> /dev/null || echo work)"
  cache_file="${cache_dir}/gh_picker_${mode}.tsv"
  patcher="$(cd "$(dirname "$0")" && pwd)/lib/gh_patch_picker_cache.py"
  if [ -x "$patcher" ] && [ -f "$cache_file" ]; then
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
    repo_path="$(resolve_repo_path "$repo_nwo")"
    if [ ! -d "$repo_path" ] || [ ! -e "$repo_path/.git" ]; then
      bootstrap_repo "$repo_nwo"
      repo_path="$(resolve_repo_path "$repo_nwo")"
    fi

    if [ ! -d "$repo_path" ]; then
      die "could not find repo at: $repo_path"
    fi

    cd "$repo_path"

    case "$kind" in
      pr)
        ,w prs --focus "$number"
        _mark_local_in_cache "pr" "$repo_nwo" "$number"
        ;;
      issue)
        ,w issue --focus "$number"
        _mark_local_in_cache "issue" "$repo_nwo" "$number"
        ;;
      *)
        die "unknown kind: $kind"
        ;;
    esac

    if [ "$action" = "octo" ] && [ "$kind" = "pr" ]; then
      if command -v nvim > /dev/null 2>&1; then
        wt_cwd="$(,w prs -q "$number" 2> /dev/null || true)"
        [ -n "$wt_cwd" ] || wt_cwd="$(pwd)"
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
