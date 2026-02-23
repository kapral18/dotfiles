#!/usr/bin/env bash
set -euo pipefail

trap 'exit 0' INT HUP TERM

die() {
  tmux display-message "$1"
  exit 0
}

need_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    die "tmux: missing command: ${cmd}"
  fi
}

normalize() {
  cat | tr ' .:' '-' | tr '[:upper:]' '[:lower:]'
}

tmux_opt() {
  local key="$1"
  local default_value="$2"
  local value
  value="$(tmux show-option -gqv "${key}")"
  if [[ -n "${value}" ]]; then
    echo "${value}"
  else
    echo "${default_value}"
  fi
}

session_name() {
  if [ "$1" = "--directory" ]; then
    shift
    basename "$@" | normalize
  elif [ "$1" = "--full-path" ]; then
    shift
    echo "$@" | normalize | sed 's/\\/$//'
  elif [ "$1" = "--short-path" ]; then
    shift
    echo "$(echo "${@%/*}" | sed -E 's;/([^/]{1,2})[^/]*;/\\1;g' | normalize)/$(basename "$@" | normalize)"
  else
    return 1
  fi
}

need_cmd fzf
need_cmd tmux

if [[ -z "${TMUX:-}" ]]; then
  die "tmux: not running inside tmux"
fi

items_cmd="$HOME/.config/tmux/scripts/pick_session_items.sh"
if [ ! -x "$items_cmd" ]; then
  die "tmux: missing script: $items_cmd"
fi

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
mkdir -p "$cache_dir" 2>/dev/null || true
sel_tmp="${cache_dir}/pick_session_fzf_selected.tsv"

kill_cmd="$HOME/.config/tmux/scripts/pick_session_action_kill_sessions.sh"
rm_cmd="$HOME/.config/tmux/scripts/pick_session_action_remove_worktrees.sh"
live_refresh_cmd="$HOME/.config/tmux/scripts/pick_session_live_refresh.sh"
hide_selected_cmd="$HOME/.config/tmux/scripts/pick_session_items_hide_selected.sh"

fzf_args="$(tmux_opt '@pick_session_fzf_options' '')"
fzf_prompt="$(tmux_opt '@pick_session_fzf_prompt' '󰍉  ')"
fzf_ghost="$(tmux_opt '@pick_session_fzf_ghost' 'filter sessions, worktrees, dirs')"
fzf_color="$(tmux_opt '@pick_session_fzf_color' 'prompt:111,query:223,input-bg:-1,input-fg:252,ghost:240,header:244,spinner:110,info:244,pointer:81,marker:214')"
fzf_ui_args=()
[ -n "$fzf_prompt" ] && fzf_ui_args+=( --prompt "$fzf_prompt" )
[ -n "$fzf_ghost" ] && fzf_ui_args+=( --ghost "$fzf_ghost" )
[ -n "$fzf_color" ] && fzf_ui_args+=( --color "$fzf_color" )
query="$*"

  pick="$(
    # shellcheck disable=SC2086
    "$items_cmd" | FZF_DEFAULT_OPTS="" fzf \
      --ansi \
      --height=100% \
      --listen \
      --no-preview \
      --scheme=path \
      --filepath-word \
      --reverse \
      --tiebreak=index \
      --delimiter=$'\t' \
      --nth=1 \
      --with-nth=1 \
      --multi \
      "${fzf_ui_args[@]}" \
      --query "$query" \
      --bind "start:execute-silent:$live_refresh_cmd >/dev/null 2>&1 &" \
      --bind "ctrl-r:reload($items_cmd)" \
      --bind "alt-r:execute-silent:$live_refresh_cmd --once --force >/dev/null 2>&1 &" \
      --bind "ctrl-x:execute-silent(cp {+f} $(printf %q "$sel_tmp"))+reload($hide_selected_cmd $(printf %q "$sel_tmp") kill)+execute-silent($kill_cmd $(printf %q "$sel_tmp"))+reload($items_cmd)+clear-selection" \
      --bind "alt-x:execute-silent(cp {+f} $(printf %q "$sel_tmp"))+reload($hide_selected_cmd $(printf %q "$sel_tmp") remove)+execute-silent($rm_cmd $(printf %q "$sel_tmp") >/dev/null 2>&1 &)+clear-selection" \
      --header "enter=open  tab=multi  ctrl-r=reload  alt-r=refresh  ctrl-x=kill-session  alt-x=remove-worktree" \
      ${fzf_args} \
    || true
  )"

if [ -z "$pick" ]; then
  exit 0
fi

selections="$pick"
if [ -z "$selections" ]; then
  exit 0
fi

repo_root_worktree_dir() {
  local common
  common="$(git rev-parse --git-common-dir 2>/dev/null || true)"
  [ -n "$common" ] || return 1
  common="$(realpath "$common" 2>/dev/null || printf '%s' "$common")"
  dirname "$common"
}

mark_lazy_split_pending() {
  local target="$1"
  tmux set-option -t "$target" -q "@pick_session_lazy_split_pending" "1" >/dev/null 2>&1 || true
}

clear_lazy_split_pending() {
  local target="$1"
  tmux set-option -t "$target" -q "@pick_session_lazy_split_pending" "0" >/dev/null 2>&1 || true
}

mark_lazy_spawn_pending() {
  local target="$1"
  tmux set-option -t "$target" -q "@pick_session_lazy_spawn_pending" "1" >/dev/null 2>&1 || true
}

split_first_window_in_session() {
  local name="$1"
  local dir="$2"
  local win panes

  win="$(tmux list-windows -t "$name" -F '#{window_id}' 2>/dev/null | head -n 1)"
  [ -n "$win" ] || win="${name}:"
  panes="$(tmux display-message -p -t "$win" '#{window_panes}' 2>/dev/null || printf '0')"
  case "$panes" in
    ''|*[!0-9]*) panes=0 ;;
  esac
  if [ "$panes" -ge 2 ]; then
    clear_lazy_split_pending "$name"
    return 0
  fi

  tmux split-window -h -t "$win" -c "$dir"
  tmux select-layout -t "$win" even-horizontal >/dev/null 2>&1 || true
  clear_lazy_split_pending "$name"
}

ensure_session_layout() {
  local name="$1"
  local dir="$2"
  local layout="${3:-two-pane}"

  if tmux has-session -t "$name" 2>/dev/null; then
    return 0
  fi

  if [ "$layout" = "deferred" ]; then
    # Bulk session creation can freeze the UI if many shells render prompts at
    # once (for example starship git metrics in very large repos). Create a
    # placeholder pane first, and let the session-change hook respawn it into
    # the real shell + layout when you actually enter the session.
    tmux new-session -d -s "$name" -c "$dir" /usr/bin/tail -f /dev/null
    mark_lazy_spawn_pending "$name"
    mark_lazy_split_pending "$name"
    return 0
  fi

  tmux new-session -d -s "$name" -c "$dir"
  split_first_window_in_session "$name" "$dir"
}

git_head_branch() {
  local dir="$1"
  git -C "$dir" symbolic-ref --quiet --short HEAD 2>/dev/null || true
}

repo_display_for_worktree_root() {
  local wt_root="$1"
  local repo_name root_branch

  repo_name="$(basename "$wt_root")"
  root_branch="$(git_head_branch "$wt_root")"
  if [ -n "$root_branch" ] && [ "$repo_name" = "$root_branch" ]; then
    repo_name="$(basename "$(dirname "$wt_root")")"
  fi
  printf '%s\n' "$repo_name"
}

remove_paths_in_background() {
  local start_dir="$1"
  shift
  local -a paths=( "$@" )
  [ ${#paths[@]} -eq 0 ] && return 0

  if ! command -v ,w >/dev/null 2>&1; then
    tmux display-message "tmux: missing command: ,w"
    return 0
  fi

  # Run in the repo context we were launched from.
  local cmd
  cmd="cd $(printf %q "$start_dir") && ,w remove --tmux-notify --paths"
  local p
  for p in "${paths[@]}"; do
    cmd+=" $(printf %q "$p")"
  done
  tmux run-shell -b "$cmd"
}

MODE="$(tmux_opt "@pick_session_mode" "directory")"

selection_count="$(printf '%s\n' "$selections" | awk 'NF { c++ } END { print c + 0 }')"
create_layout="two-pane"
if [ "${selection_count:-0}" -gt 1 ]; then
  create_layout="deferred"
fi
target_session=""
while IFS=$'\t' read -r _display kind path meta target; do
  case "$kind" in
    session)
      target_session="$target"
      # If this session was discovered via a worktree and it has a preferred
      # name, rename it on-demand so the tmux session list matches the picker.
      case "$meta" in
        sess_root:*|sess_wt:*)
          if [[ "$meta" == *"|expected="* ]]; then
            expected="${meta#*|expected=}"
            if [ -n "$expected" ] && [ "$expected" != "$target_session" ]; then
              if ! tmux has-session -t "$expected" 2>/dev/null; then
                tmux rename-session -t "$target_session" "$expected" 2>/dev/null || true
                target_session="$expected"
              fi
            fi
          fi
          ;;
      esac
      ;;
    worktree)
      [ -n "$path" ] || continue
      [ -d "$path" ] || continue
      branch="${meta#wt_root:}"
      branch="${branch#wt:}"
      session_name=""
      wt_root="$target"
      if [ -z "$wt_root" ]; then
        wt_root="$(git -C "$path" rev-parse --git-common-dir 2>/dev/null | { read -r c; [ -n "$c" ] || exit 0; case "$c" in /*) dirname "$c" ;; *) dirname "$path/$c" ;; esac; } )"
      fi
      repo_name=""
      if [ -n "$wt_root" ]; then
        wt_root="$(realpath "$wt_root" 2>/dev/null || printf '%s' "$wt_root")"
        repo_name="$(repo_display_for_worktree_root "$wt_root")"
      fi

      if [ -n "$branch" ] && [ -n "$repo_name" ]; then
        session_name="${repo_name}|${branch}"
      elif [ -n "$branch" ]; then
        session_name="$branch"
      else
        session_name="$(basename "$path")"
      fi
      ensure_session_layout "$session_name" "$path" "$create_layout"
      target_session="$session_name"
      ;;
    dir)
      [ -n "$path" ] || continue
      [ -d "$path" ] || continue
      dir_with_tilde="$path"
      # shellcheck disable=SC2088
      case "$path" in
        "$HOME") dir_with_tilde="~" ;;
        "$HOME"/*) dir_with_tilde="~/${path#"$HOME"/}" ;;
      esac
      session="$(session_name --"${MODE}" "${dir_with_tilde}")"
      ensure_session_layout "$session" "$path" "$create_layout"
      target_session="$session"
      ;;
    *)
      continue
      ;;
  esac
done <<<"$selections"

if [ -z "$target_session" ]; then
  exit 0
fi

if [ "$target_session" = "~" ]; then
  target_session="\\~"
fi
tmux switch-client -t "${target_session}"
