#!/usr/bin/env bash
if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
  _b="$(brew --prefix bash 2>/dev/null)/bin/bash"
  [ -x "$_b" ] && exec "$_b" "$0" "$@"
  exit 1
fi
set -euo pipefail

sel_file="${1:-}"
cmd_file="${2:-}"

if [ -z "$sel_file" ] || [ ! -f "$sel_file" ]; then
  exit 0
fi
if [ -z "$cmd_file" ] || [ ! -f "$cmd_file" ]; then
  exit 0
fi

cmd="$(cat "$cmd_file" 2>/dev/null || true)"
rm -f "$cmd_file" 2>/dev/null || true

if [ -z "$cmd" ]; then
  exit 0
fi

declare -a sess=()
declare -a paths_to_check=()

while IFS= read -r _line; do
  [ -n "$_line" ] || continue
  mapfile -t _fields < <(awk -F $'\t' '{print $1; print $2; print $3; print $4; print $5}' <<<"$_line")
  kind="${_fields[1]-}"
  path="${_fields[2]-}"
  target="${_fields[4]-}"

  if [ "$kind" = "session" ] && [ -n "$target" ]; then
    sess+=("$target")
  elif [ "$kind" = "dir" ] || [ "$kind" = "worktree" ]; then
    if [ -n "$path" ]; then
      paths_to_check+=("$path")
    fi
  fi
done <"$sel_file"

if [ ${#paths_to_check[@]} -gt 0 ] && command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
  while IFS=$'\t' read -r name spath; do
    [ -n "$name" ] || continue
    [ -n "$spath" ] || continue
    spath="$(realpath "$spath" 2>/dev/null || printf '%s' "$spath")"
    for d in "${paths_to_check[@]}"; do
      rd="$(realpath "$d" 2>/dev/null || printf '%s' "$d")"
      if [ "$spath" = "$rd" ] || [[ "$spath" == "$rd"/* ]]; then
        sess+=("$name")
        break
      fi
    done
  done < <(tmux list-sessions -F $'#{session_name}\t#{session_path}' 2>/dev/null || true)
fi

if [ ${#sess[@]} -gt 0 ]; then
  mapfile -t sess < <(printf '%s\n' "${sess[@]}" | sort -u)
fi

if [ ${#sess[@]} -eq 0 ]; then
  exit 0
fi

for s in "${sess[@]}"; do
  panes="$(tmux list-panes -s -t "$s" -F '#{window_index}.#{pane_index} #{pane_current_command}' 2>/dev/null || true)"

  target_pane=""
  while read -r pane_id p_cmd; do
    case "$p_cmd" in
    fish | zsh | bash | sh)
      target_pane="$pane_id"
      break
      ;;
    esac
  done <<<"$panes"

  if [ -z "$target_pane" ]; then
    target_pane="$(tmux list-panes -s -t "$s" -F '#{window_index}.#{pane_index}' 2>/dev/null | head -n 1)"
  fi

  if [ -n "$target_pane" ]; then
    tmux send-keys -t "=${s}:${target_pane}" "$cmd" C-m
  fi
done
