#!/usr/bin/env bash
# Worktree helper functions library

_f_wtree_prune_stale_worktrees() {
  if [ "${__F_WTREE_PRUNE_RAN:-0}" -eq 1 ]; then
    return
  fi
  __F_WTREE_PRUNE_RAN=1

  case "${F_WTREE_PRUNE:-1}" in
    0|false|no|off)
      return
      ;;
  esac

  local dry_run_output
  dry_run_output="$(git worktree prune --dry-run 2>&1 || true)"
  if [ -z "${dry_run_output//[[:space:]]/}" ]; then
    return
  fi

  if [ "${QUIET_MODE:-0}" -eq 0 ]; then
    echo "Pruning stale git worktree metadata..."
  fi

  git worktree prune 2>&1 || true
}

# Print created worktree message
_print_created_worktree_message() {
  if [ "${QUIET_MODE:-0}" -eq 1 ]; then
    return
  fi

  echo "

-------------

Created new worktree
For Branch: $1
At Path: $2"

  if [ -n "${3:-}" ]; then
    echo "From Branch: $3"
  else
    echo "From Current Branch"
  fi
}

# Add worktree tmux session
_add_worktree_tmux_session() {
  if [ -n "${TMUX:-}" ]; then
    if [ "${QUIET_MODE:-0}" -eq 0 ]; then
      echo "

-------------

Adding TMUX Session: $1|$2
At Path: $3
"
    fi
    # add tmux session
    tmux new-session -d -s "$1|$2" -c "$3"
  fi
}

# Remove worktree tmux session
_remove_worktree_tmux_session() {
  if [ -n "${TMUX:-}" ]; then
    local worktree_path="$1"
    local session_name

    session_name=$(tmux list-sessions -F "#{session_name} #{session_path}" | grep -i "$worktree_path" | awk '{print $1}')

    if [ "${QUIET_MODE:-0}" -eq 0 ]; then
      echo "

-------------

Removing TMUX Session: $session_name
"
    fi
    if [ -n "$session_name" ]; then
      tmux kill-session -t "$session_name"
    fi
  fi
}
