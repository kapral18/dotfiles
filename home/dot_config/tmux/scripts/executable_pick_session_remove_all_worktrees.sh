#!/usr/bin/env bash
set -euo pipefail

root_wt_dir="${1:-}"
if [ -z "$root_wt_dir" ]; then
  exit 0
fi

cd "$root_wt_dir"
root="$(pwd -P)"

common="$(realpath "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null || true)"
if [ -z "$common" ]; then
  exit 0
fi

# `parent` is the directory containing all worktrees (sibling dirs of the root worktree).
parent="$(dirname "$(dirname "$common")")"

if [ -n "${TMUX:-}" ] && command -v tmux >/dev/null 2>&1; then
  tmux display-message -d 6000 "pick_session: removing all worktrees for $root" 2>/dev/null || true
fi

git worktree list --porcelain | awk '/^worktree /{print $2}' | while IFS= read -r p; do
  [ -z "$p" ] && continue
  rp="$(realpath "$p" 2>/dev/null || printf '%s' "$p")"
  [ "$rp" = "$root" ] && continue
  case "$rp" in
    */.git/*|*/.git) continue ;;
  esac

  if [ -n "${TMUX:-}" ] && command -v tmux >/dev/null 2>&1; then
    tmux list-sessions -F $'#{session_name}\t#{session_path}' 2>/dev/null |
      while IFS=$'\t' read -r sname spath; do
        [ -z "$sname" ] && continue
        [ -z "$spath" ] && continue
        spath="$(realpath "$spath" 2>/dev/null || printf '%s' "$spath")"
        if [ "$spath" = "$rp" ]; then
          tmux kill-session -t "$sname" 2>/dev/null || true
        fi
      done
  fi

  rm -rf "$rp"

  cur="$(dirname "$rp")"
  while [ "$cur" != "/" ] && [ "$cur" != "$parent" ]; do
    if [ -n "$(ls -A "$cur" 2>/dev/null)" ]; then
      break
    fi
    rmdir "$cur" 2>/dev/null || break
    cur="$(dirname "$cur")"
  done

  if [ -n "${TMUX:-}" ] && command -v tmux >/dev/null 2>&1; then
    tmux display-message -d 6000 "pick_session: removed $rp" 2>/dev/null || true
  fi
done

