#!/usr/bin/env bash
set -euo pipefail

if [ -f "${1:-}" ]; then
  line="$(head -n 1 "$1" 2> /dev/null || true)"
else
  line="${1:-}"
fi
[ -n "$line" ] || exit 0

kind="$(printf '%s' "$line" | awk -F $'\t' '{print $2}')"
path="$(printf '%s' "$line" | awk -F $'\t' '{print $3}')"
target="$(printf '%s' "$line" | awk -F $'\t' '{print $5}')"

C_DIM=$'\033[2m'
C_BOLD=$'\033[1m'
C_BLUE=$'\033[38;5;111m'
C_GREEN=$'\033[38;5;150m'
C_YELLOW=$'\033[38;5;214m'
C_CYAN=$'\033[38;5;81m'
C_R=$'\033[0m'

header() {
  printf '%s%s%s\n' "$C_BOLD$C_CYAN" "$1" "$C_R"
}

dim() {
  printf '%s%s%s' "$C_DIM" "$1" "$C_R"
}

git_summary() {
  local dir="$1"
  [ -d "$dir" ] || return 0
  [ -e "$dir/.git" ] || return 0

  if ! git -C "$dir" rev-parse --git-dir > /dev/null 2>&1; then
    printf '%s  %s%s%s\n' "$(dim 'git')" "$C_YELLOW" "stale worktree (gitdir missing)" "$C_R"
    printf '\n%s\n' "$(header 'contents')"
    ls -1 --color=always "$dir" 2> /dev/null | head -20 || ls -1 "$dir" 2> /dev/null | head -20 || true
    return 0
  fi

  local branch status_lines log_lines

  branch="$(git -C "$dir" symbolic-ref --quiet --short HEAD 2> /dev/null || git -C "$dir" rev-parse --short HEAD 2> /dev/null || true)"
  if [ -n "$branch" ]; then
    printf '%s  %s%s%s\n' "$(dim 'branch')" "$C_GREEN" "$branch" "$C_R"
  fi

  local ahead behind
  ahead="$(git -C "$dir" rev-list --count '@{upstream}..HEAD' 2> /dev/null || true)"
  behind="$(git -C "$dir" rev-list --count 'HEAD..@{upstream}' 2> /dev/null || true)"
  if [ "${ahead:-0}" != "0" ] || [ "${behind:-0}" != "0" ]; then
    printf '%s  ' "$(dim 'sync')"
    [ "${ahead:-0}" != "0" ] && printf '%s↑%s%s ' "$C_YELLOW" "$ahead" "$C_R"
    [ "${behind:-0}" != "0" ] && printf '%s↓%s%s ' "$C_BLUE" "$behind" "$C_R"
    printf '\n'
  fi

  status_lines="$(git -C "$dir" status --porcelain 2> /dev/null | head -8 || true)"
  if [ -n "$status_lines" ]; then
    local total
    total="$(git -C "$dir" status --porcelain 2> /dev/null | wc -l | tr -d ' ')"
    printf '\n%s\n' "$(header "changes ($total)")"
    printf '%s\n' "$status_lines"
    [ "$total" -gt 8 ] 2> /dev/null && printf '%s\n' "$(dim "  … and $((total - 8)) more")"
  fi

  log_lines="$(git -C "$dir" log --oneline --no-decorate -6 2> /dev/null || true)"
  if [ -n "$log_lines" ]; then
    printf '\n%s\n' "$(header 'recent commits')"
    printf '%s\n' "$log_lines"
  fi
}

pane_capture() {
  local sess="$1"
  [ -n "$sess" ] || return 0

  local pane_info active_cmd
  pane_info="$(tmux list-panes -t "$sess" -F '#{pane_index} #{pane_current_command} #{pane_pid}' 2> /dev/null | head -1 || true)"
  if [ -n "$pane_info" ]; then
    active_cmd="$(printf '%s' "$pane_info" | awk '{print $2}')"
    if [ -n "$active_cmd" ]; then
      printf '%s  %s%s%s\n' "$(dim 'running')" "$C_YELLOW" "$active_cmd" "$C_R"
    fi
  fi

  local sess_path
  sess_path="$(tmux display-message -t "$sess" -p '#{session_path}' 2> /dev/null || true)"
  if [ -n "$sess_path" ]; then
    local tpath="$sess_path"
    case "$sess_path" in
      "$HOME") tpath="~" ;;
      "$HOME"/*) tpath="~/${sess_path#"$HOME"/}" ;;
    esac
    printf '%s  %s%s%s\n' "$(dim 'path')" "$C_BLUE" "$tpath" "$C_R"
  fi

  local windows
  windows="$(tmux list-windows -t "$sess" -F '#{window_index}:#{window_name} #{window_active}' 2> /dev/null || true)"
  local win_count
  win_count="$(printf '%s\n' "$windows" | grep -c . || true)"
  if [ "${win_count:-0}" -gt 1 ]; then
    printf '%s  %s windows\n' "$(dim 'layout')" "$win_count"
  fi

  local pane_text
  pane_text="$(tmux capture-pane -t "$sess" -p 2> /dev/null | awk 'NF{p=1} p' || true)"
  if [ -n "$pane_text" ]; then
    printf '\n%s\n' "$(header 'pane content')"
    printf '%s\n' "$pane_text" | tail -20
  else
    printf '\n%s\n' "$(dim '(empty pane)')"
  fi
}

dir_preview() {
  local dir="$1"
  [ -d "$dir" ] || {
    printf 'directory not found: %s\n' "$dir"
    return 0
  }

  local tpath="$dir"
  case "$dir" in
    "$HOME") tpath="~" ;;
    "$HOME"/*) tpath="~/${dir#"$HOME"/}" ;;
  esac
  printf '%s  %s%s%s\n' "$(dim 'path')" "$C_BLUE" "$tpath" "$C_R"

  if [ -e "$dir/.git" ]; then
    git_summary "$dir"
  else
    printf '\n%s\n' "$(header 'contents')"
    ls -1 --color=always "$dir" 2> /dev/null | head -20 || ls -1 "$dir" 2> /dev/null | head -20 || true
  fi
}

case "$kind" in
  session)
    if [ -n "$target" ]; then
      pane_capture "$target"
    elif [ -n "$path" ] && [ -d "$path" ]; then
      dir_preview "$path"
    fi
    ;;
  worktree)
    if [ -n "$path" ] && [ -d "$path" ]; then
      dir_preview "$path"
    fi
    ;;
  dir)
    if [ -n "$path" ] && [ -d "$path" ]; then
      dir_preview "$path"
    fi
    ;;
  *)
    printf '%s\n' "$line"
    ;;
esac
