#!/usr/bin/env bash
# Worktree helper functions library

_comma_w_prune_stale_worktrees() {
  local quiet_mode="${1:-0}"
  if [ "${__COMMA_W_PRUNE_RAN:-0}" -eq 1 ]; then
    return
  fi
  __COMMA_W_PRUNE_RAN=1

  case "${COMMA_W_PRUNE:-1}" in
  0 | false | no | off)
    return
    ;;
  esac

  local dry_run_output
  dry_run_output="$(git worktree prune --dry-run 2>&1 || true)"
  if [ -z "${dry_run_output//[[:space:]]/}" ]; then
    return
  fi

  if [ "$quiet_mode" -eq 0 ]; then
    echo "Pruning stale git worktree metadata..."
  fi

  git worktree prune 2>&1 || true
}

# Print created worktree message
_print_created_worktree_message() {
  local quiet_mode="${1:-0}"
  local branch_name="$2"
  local worktree_path="$3"
  local from_branch="${4:-}"

  if [ "$quiet_mode" -eq 1 ]; then
    return
  fi

  echo "

-------------

Created new worktree
For Branch: $branch_name
At Path: $worktree_path"

  if [ -n "$from_branch" ]; then
    echo "From Branch: $from_branch"
  else
    echo "From Current Branch"
  fi
}

_comma_w_tmux_session_name() {
  local parent_name="$1"
  local branch_name="$2"
  printf '%s|%s\n' "$parent_name" "$branch_name"
}

# Add worktree tmux session
_add_worktree_tmux_session() {
  local quiet_mode="${1:-0}"
  local parent_name="$2"
  local branch_name="$3"
  local worktree_path="$4"

  if [ -n "${TMUX:-}" ]; then
    if ! command -v tmux >/dev/null 2>&1; then
      if [ "$quiet_mode" -eq 0 ]; then
        echo "Warning: TMUX is set but 'tmux' is not available; skipping session creation." >&2
      fi
      return 0
    fi

    if [ "$quiet_mode" -eq 0 ]; then
      echo "

-------------

Adding TMUX Session: $parent_name|$branch_name
At Path: $worktree_path
"
    fi

    local session_name
    session_name="$(_comma_w_tmux_session_name "$parent_name" "$branch_name")"
    if tmux has-session -t "$session_name" 2>/dev/null; then
      return 0
    fi

    if ! tmux new-session -d -s "$session_name" -c "$worktree_path" 2>/dev/null; then
      if [ "$quiet_mode" -eq 0 ]; then
        echo "Warning: Failed to create tmux session '$session_name'." >&2
      fi
    fi
  fi
}

# Remove worktree tmux session
_remove_worktree_tmux_session() {
  if [ -n "${TMUX:-}" ]; then
    local quiet_mode="${1:-0}"
    local worktree_path="$2"
    local session_name_hint="${3:-}"
    local -a session_names=()
    local session_name
    local session_path

    if [ -n "$session_name_hint" ] && tmux has-session -t "$session_name_hint" 2>/dev/null; then
      session_names+=("$session_name_hint")
    fi

    while IFS=$'\t' read -r session_name session_path; do
      if [ "$session_path" = "$worktree_path" ]; then
        session_names+=("$session_name")
      fi
    done < <(tmux list-sessions -F $'#{session_name}\t#{session_path}' 2>/dev/null || true)

    if [ "$quiet_mode" -eq 0 ]; then
      echo "

-------------

Removing TMUX Session: ${session_names[*]:-}
"
    fi
    for session_name in "${session_names[@]}"; do
      tmux kill-session -t "$session_name" 2>/dev/null || true
    done
  fi
}

_comma_w_find_worktree_path_for_branch() {
  local branch="$1"
  local line
  local worktree_path=""
  local target="branch refs/heads/${branch}"

  while IFS= read -r line; do
    case "$line" in
    worktree\ *)
      worktree_path="${line#worktree }"
      ;;
    "$target")
      if [ -n "$worktree_path" ]; then
        printf '%s\n' "$worktree_path"
        return 0
      fi
      ;;
    esac
  done < <(git worktree list --porcelain)

  return 1
}

_comma_w_focus_tmux_session() {
  local quiet_mode="${1:-0}"
  local session_name="$2"
  local worktree_path="$3"

  if ! command -v tmux >/dev/null 2>&1; then
    if [ "$quiet_mode" -eq 0 ]; then
      echo "Warning: 'tmux' is not available; cannot focus session '$session_name'." >&2
    fi
    return 1
  fi

  if [ -n "${TMUX:-}" ]; then
    tmux switch-client -t "$session_name" 2>/dev/null || true
    return 0
  fi

  tmux attach-session -t "$session_name" 2>/dev/null || tmux new-session -s "$session_name" -c "$worktree_path"
}
