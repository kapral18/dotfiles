#!/usr/bin/env bash
# Worktree helper functions library

# Print created worktree message
_print_created_worktree_message() {
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
    echo "

-------------

Adding TMUX Session: $1|$2
At Path: $3
"
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

    echo "

-------------

Removing TMUX Session: $session_name
"
    if [ -n "$session_name" ]; then
      tmux kill-session -t "$session_name"
    fi
  fi
}

