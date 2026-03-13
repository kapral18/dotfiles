#!/usr/bin/env bash
# Re-exec under a modern bash when macOS ships bash 3.2 as /bin/bash.
if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
  _b="$(brew --prefix bash 2>/dev/null)/bin/bash"
  [ -x "$_b" ] && exec "$_b" "$0" "$@"
  exit 1
fi
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
  cat |
    tr ' .:/' '-' |
    tr '[:upper:]' '[:lower:]' |
    sed -E 's/-+/-/g; s/^-+//; s/-+$//'
}

tmux_sanitize_session_name() {
  # tmux normalizes some characters in session names (notably '.'). Do minimal
  # sanitization so the name we target is the name tmux will actually create,
  # while preserving common branch separators like '/'.
  local s="${1-}"
  [ -n "$s" ] || return 1
  printf '%s\n' "$s" |
    tr '[:upper:]' '[:lower:]' |
    sed -E 's/[^a-z0-9_@|/~-]+/_/g; s/[.:]+/_/g; s/_+$//'
}

_tmux_gopts_cache=""
_tmux_gopts_loaded=0

tmux_opt() {
  local key="$1"
  local default_value="$2"
  if [ "$_tmux_gopts_loaded" -eq 0 ]; then
    _tmux_gopts_cache="$(tmux show-options -g 2>/dev/null || true)"
    _tmux_gopts_loaded=1
  fi
  local value="" line
  while IFS= read -r line; do
    case "$line" in
    "$key "*)
      value="${line#"$key "}"
      break
      ;;
    esac
  done <<<"$_tmux_gopts_cache"
  # show-options -g preserves tmux quoting ('...' / "..."); strip it to match
  # the behaviour of show-option -gqv.
  local _q="'"
  case "$value" in
  \"*\")
    value="${value#\"}"
    value="${value%\"}"
    ;;
  "$_q"*"$_q")
    value="${value#"$_q"}"
    value="${value%"$_q"}"
    ;;
  esac
  printf '%s\n' "${value:-$default_value}"
}

session_name() {
  if [ "$1" = "--directory" ]; then
    shift
    input="${1-}"
    base="$(basename "$input")"
    case "$input" in
    "~") base="home" ;;
    *) if [ "$base" = "~" ]; then base="tilde"; fi ;;
    esac
    out="$(printf '%s\n' "$base" | normalize)"
    case "$out" in
    "" | "~") out="home" ;;
    esac
    printf '%s\n' "$out"
  elif [ "$1" = "--full-path" ]; then
    shift
    out="$(echo "$@" | normalize | sed 's/\\/$//')"
    case "$out" in
    "" | "~") out="home" ;;
    esac
    echo "$out"
  elif [ "$1" = "--short-path" ]; then
    shift
    left="$(echo "${@%/*}" | sed -E 's;/([^/]{1,2})[^/]*;/\\1;g' | normalize)"
    right="$(basename "$@" | normalize)"
    case "$right" in
    "" | "~") right="home" ;;
    esac
    echo "${left}/${right}"
  else
    return 1
  fi
}

need_cmd fzf
need_cmd tmux

if [[ -z "${TMUX:-}" ]]; then
  die "tmux: not running inside tmux"
fi

bulk_guard_key="@pick_session_bulk_create_in_progress"
bulk_guard_set() {
  tmux set-option -gq "$bulk_guard_key" "1" >/dev/null 2>&1 || true
}
bulk_guard_clear() {
  tmux set-option -gq "$bulk_guard_key" "0" >/dev/null 2>&1 || true
}
bulk_guard_set
trap 'bulk_guard_clear; exit 0' EXIT

__sess_cache_loaded=0
sess_names=()
sess_paths=()
sess_rpaths=()

sess_cache_load() {
  local out n p rp
  out="$(tmux list-sessions -F $'#{session_name}\t#{session_path}' 2>/dev/null || true)"
  sess_names=()
  sess_paths=()
  sess_rpaths=()
  while IFS=$'\t' read -r n p; do
    [ -n "$n" ] || continue
    [ -n "$p" ] || continue
    rp="$(resolve_path "$p" 2>/dev/null || printf '%s' "$p")"
    sess_names+=("$n")
    sess_paths+=("$p")
    sess_rpaths+=("$rp")
  done <<<"$out"
  __sess_cache_loaded=1
}

sess_index_for_name() {
  local name="$1"
  [ -n "$name" ] || return 1
  local i
  for i in "${!sess_names[@]}"; do
    if [ "${sess_names[$i]}" = "$name" ]; then
      printf '%s\n' "$i"
      return 0
    fi
  done
  return 1
}

sess_has_name() {
  local name="$1"
  sess_index_for_name "$name" >/dev/null 2>&1
}

sess_path_for_name() {
  local name="$1"
  local i
  i="$(sess_index_for_name "$name" 2>/dev/null || true)"
  [ -n "$i" ] || return 1
  printf '%s\n' "${sess_paths[$i]}"
}

sess_name_for_rpath() {
  local rp="$1"
  [ -n "$rp" ] || return 1
  local i
  for i in "${!sess_rpaths[@]}"; do
    if [ "${sess_rpaths[$i]}" = "$rp" ]; then
      printf '%s\n' "${sess_names[$i]}"
      return 0
    fi
  done
  return 1
}

sess_add() {
  local name="$1"
  local path="$2"
  [ -n "$name" ] || return 1
  [ -n "$path" ] || return 1
  sess_names+=("$name")
  sess_paths+=("$path")
  sess_rpaths+=("$(resolve_path "$path" 2>/dev/null || printf '%s' "$path")")
}

sess_rename() {
  local old="$1"
  local new="$2"
  [ -n "$old" ] || return 1
  [ -n "$new" ] || return 1
  local i
  i="$(sess_index_for_name "$old" 2>/dev/null || true)"
  [ -n "$i" ] || return 1
  sess_names[$i]="$new"
}

tmux_has_session_exact() {
  local name="$1"
  [ -n "$name" ] || return 1
  if [ "${__sess_cache_loaded:-0}" -eq 1 ]; then
    sess_has_name "$name"
    return $?
  fi
  tmux has-session -t "=${name}" 2>/dev/null
}

items_cmd="$HOME/.config/tmux/scripts/pick_session/items.sh"
if [ ! -x "$items_cmd" ]; then
  die "tmux: missing script: $items_cmd"
fi

open_items_cmd="$HOME/.config/tmux/scripts/pick_session/open_items.sh"
if [ ! -x "$open_items_cmd" ]; then
  open_items_cmd="$items_cmd"
fi

filter_cmd="$HOME/.config/tmux/scripts/pick_session/filter.sh"
if [ ! -x "$filter_cmd" ]; then
  filter_cmd="$items_cmd"
fi

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
mkdir -p "$cache_dir" 2>/dev/null || true
sel_tmp="${cache_dir}/pick_session_fzf_selected.tsv"
primary_tmp="${cache_dir}/pick_session_fzf_primary.tsv"

kill_cmd="$HOME/.config/tmux/scripts/pick_session/action_kill_sessions.sh"
rm_cmd="$HOME/.config/tmux/scripts/pick_session/action_remove_worktrees.sh"
live_refresh_cmd="$HOME/.config/tmux/scripts/pick_session/live_refresh.sh"
hide_selected_cmd="$HOME/.config/tmux/scripts/pick_session/items_hide_selected.sh"
update_cmd="$HOME/.config/tmux/scripts/pick_session/index_update.sh"
kill_async_cmd="tmux run-shell -b \"$(printf %q "$kill_cmd") $(printf %q "$sel_tmp")\""
rm_async_cmd="tmux run-shell -b \"$(printf %q "$rm_cmd") $(printf %q "$sel_tmp")\""

send_cmd="$HOME/.config/tmux/scripts/pick_session/action_send_command.sh"
cmd_tmp="${cache_dir}/pick_session_cmd.txt"
mode_flag="${cache_dir}/pick_session_send_mode"

fzf_args="$(tmux_opt '@pick_session_fzf_options' '')"
fzf_prompt="$(tmux_opt '@pick_session_fzf_prompt' '󰍉  ')"
fzf_ghost="$(tmux_opt '@pick_session_fzf_ghost' 'filter: kibana, code, work')"
fzf_color="$(tmux_opt '@pick_session_fzf_color' 'prompt:111,query:223,input-bg:-1,input-fg:252,ghost:240,header:244,spinner:110,info:244,pointer:81,marker:214')"
fzf_ui_args=()
[ -n "$fzf_prompt" ] && fzf_ui_args+=(--prompt "$fzf_prompt")
[ -n "$fzf_ghost" ] && fzf_ui_args+=(--ghost "$fzf_ghost")
[ -n "$fzf_color" ] && fzf_ui_args+=(--color "$fzf_color")
query="$*"

help_cmd="$HOME/.config/tmux/scripts/pick_session/keyhelp.sh"
preview_cmd="$HOME/.config/tmux/scripts/pick_session/preview.sh"

# fzf send-mode: ctrl-s enters a modal where the query line becomes a command
# prompt. enter dispatches the command to selected sessions; esc cancels.
send_restore="enable-search+change-prompt($fzf_prompt)+change-ghost($fzf_ghost)+change-header(?=help  ctrl-/=preview)+clear-query+deselect-all+rebind(ctrl-s,ctrl-x,alt-x,change)+unbind(esc)"
send_mode="execute-silent(cp {+f} $sel_tmp)+execute-silent(touch $mode_flag)+disable-search+change-prompt(❯ send: )+change-ghost()+change-header(enter=send  esc=cancel)+clear-query+unbind(ctrl-s,ctrl-x,alt-x,change)+rebind(esc)"

selection_file="${PICK_SESSION_SELECTION_FILE:-}"
if [ -n "$selection_file" ] && [ -f "$selection_file" ]; then
  pick="$(cat "$selection_file" 2>/dev/null || true)"
else
  rm -f "$primary_tmp" "$cmd_tmp" "$mode_flag" 2>/dev/null || true
  # shellcheck disable=SC2086
  pick="$(
    FZF_DEFAULT_OPTS="" "$open_items_cmd" | fzf \
      --ansi \
      --scheme=path \
      --height=100% \
      --listen \
      --filepath-word \
      --reverse \
      --tiebreak=begin,length,index \
      --delimiter=$'\t' \
      --nth=1,6 \
      --with-nth=1 \
      --multi \
      "${fzf_ui_args[@]}" \
      --query "$query" \
      --preview "$preview_cmd {f}" \
      --preview-window 'right,50%,border-left' \
      --bind "ctrl-r:reload($filter_cmd --refresh --force-order)+clear-query" \
      --bind "alt-r:execute-silent:$live_refresh_cmd --once --force >/dev/null 2>&1 &" \
      --bind "alt-j:half-page-down" \
      --bind "alt-k:half-page-up" \
      --bind "alt-h:first" \
      --bind "alt-l:last" \
      --bind "shift-up:preview-up" \
      --bind "shift-down:preview-down" \
      --bind "shift-left:preview-page-up" \
      --bind "shift-right:preview-page-down" \
      --bind "ctrl-/:toggle-preview" \
      --bind "?:change-preview($help_cmd)+show-preview" \
      --bind "focus:change-preview($preview_cmd {f})" \
      --bind "change:first" \
      --bind "load:unbind(esc)" \
      --bind "enter:transform:[ -f $mode_flag ] && { printf '%s' {q} > $cmd_tmp; echo 'execute-silent(tmux run-shell -b \"$send_cmd $sel_tmp $cmd_tmp\")+execute-silent(rm -f $mode_flag)+$send_restore'; } || echo 'execute-silent(cp {f} $primary_tmp)+accept'" \
      --bind "ctrl-s:$send_mode" \
      --bind "esc:execute-silent(rm -f $mode_flag)+$send_restore" \
      --bind "ctrl-x:execute-silent(cp {+f} $(printf %q "$sel_tmp"))+reload($hide_selected_cmd $(printf %q "$sel_tmp") kill {q})+execute-silent($kill_async_cmd)+deselect-all" \
      --bind "alt-x:execute-silent(cp {+f} $(printf %q "$sel_tmp"))+reload($hide_selected_cmd $(printf %q "$sel_tmp") remove {q})+execute-silent($rm_async_cmd)+deselect-all" \
      --header $'?=help  ctrl-/=preview' \
      \
      ${fzf_args} ||
      true
  )"
fi
if [ -z "$pick" ]; then
  exit 0
fi

selections="$pick"
if [ -z "$selections" ]; then
  exit 0
fi

primary_kind=""
primary_path=""
primary_target=""
if [ -f "$primary_tmp" ]; then
  primary_line="$(cat "$primary_tmp" 2>/dev/null | head -n 1 || true)"
  if [ -n "${primary_line:-}" ]; then
    IFS=$'\t' read -r _pdisp primary_kind primary_path _pmeta primary_target _pmk <<<"$primary_line"
  fi
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
  '' | *[!0-9]*) panes=0 ;;
  esac
  if [ "$panes" -ge 2 ]; then
    clear_lazy_split_pending "$name"
    return 0
  fi

  local shell="${SHELL:-/opt/homebrew/bin/fish}"
  tmux split-window -h -t "$win" -c "$dir" "$shell" >/dev/null 2>&1 || true
  tmux select-layout -t "$win" even-horizontal >/dev/null 2>&1 || true
  clear_lazy_split_pending "$name"
}

ensure_session_layout() {
  local name="$1"
  local dir="$2"
  local layout="${3:-two-pane}"

  if tmux_has_session_exact "$name"; then
    return 0
  fi

  if [ "$layout" = "deferred" ]; then
    # Bulk session creation can freeze the UI if many shells render prompts at
    # once (for example starship git metrics in very large repos). Create a
    # placeholder pane first, and let the session-change hook respawn it into
    # the real shell + layout when you actually enter the session.
    if ! tmux new-session -d -s "$name" -c "$dir" /usr/bin/tail -f /dev/null 2>/dev/null; then
      die "tmux: failed to create session: $name ($dir)"
    fi
    created_any_session=1
    if [ "${__sess_cache_loaded:-0}" -eq 1 ]; then
      sess_add "$name" "$dir" || true
    fi
    mark_lazy_spawn_pending "$name"
    mark_lazy_split_pending "$name"
    return 0
  fi

  local shell="${SHELL:-/opt/homebrew/bin/fish}"
  if ! tmux new-session -d -s "$name" -c "$dir" "$shell" 2>/dev/null; then
    die "tmux: failed to create session: $name ($dir)"
  fi
  created_any_session=1
  if [ "${__sess_cache_loaded:-0}" -eq 1 ]; then
    sess_add "$name" "$dir" || true
  fi
  split_first_window_in_session "$name" "$dir"
}

git_head_branch() {
  local dir="$1"
  git -C "$dir" symbolic-ref --quiet --short HEAD 2>/dev/null || true
}

repo_display_for_worktree_root() {
  local wt_root="$1"
  local repo_name origin_url cfg

  cfg="$(git_config_file_for_worktree_root "$wt_root" 2>/dev/null || true)"
  if [ -n "$cfg" ] && [ -f "$cfg" ]; then
    origin_url="$(awk '
      BEGIN { sec="" }
      match($0, /^\[remote \"([^\"]+)\"\]/, m) { sec=m[1]; next }
      sec=="origin" && match($0, /^[[:space:]]*url[[:space:]]*=[[:space:]]*(.+)$/, m) { print m[1]; exit }
    ' "$cfg" 2>/dev/null || true)"
    if [ -z "${origin_url:-}" ]; then
      origin_url="$(awk '
        BEGIN { sec="" }
        match($0, /^\[remote \"([^\"]+)\"\]/, m) { sec=m[1]; next }
        sec=="upstream" && match($0, /^[[:space:]]*url[[:space:]]*=[[:space:]]*(.+)$/, m) { print m[1]; exit }
      ' "$cfg" 2>/dev/null || true)"
    fi
  fi
  if [ -n "$origin_url" ]; then
    origin_url="${origin_url%/}"
    repo_name="${origin_url##*/}"
    repo_name="${repo_name##*:}"
    repo_name="${repo_name%.git}"
  fi

  if [ -z "${repo_name:-}" ]; then
    repo_name="$(basename "$wt_root")"
    case "$repo_name" in
    main | master | trunk | develop | dev)
      repo_name="$(basename "$(dirname "$wt_root")")"
      ;;
    esac
  fi

  printf '%s\n' "${repo_name:-}"
}

resolve_path() {
  realpath "$1" 2>/dev/null || printf '%s' "$1"
}

git_config_file_for_worktree_root() {
  local wt_root="$1"
  [ -n "$wt_root" ] || return 1
  wt_root="$(resolve_path "$wt_root")"
  local gitp="$wt_root/.git"
  local first gitdir cfg
  if [ -d "$gitp" ] && [ -f "$gitp/config" ]; then
    printf '%s\n' "$gitp/config"
    return 0
  fi
  if [ -f "$gitp" ]; then
    first="$(head -n 1 "$gitp" 2>/dev/null || true)"
    case "$first" in
    gitdir:*)
      gitdir="${first#gitdir:}"
      gitdir="${gitdir#"${gitdir%%[![:space:]]*}"}"
      gitdir="${gitdir%"${gitdir##*[![:space:]]}"}"
      [ -n "$gitdir" ] || return 1
      case "$gitdir" in
      /*) ;;
      *) gitdir="$wt_root/$gitdir" ;;
      esac
      gitdir="$(resolve_path "$gitdir")"
      cfg="$gitdir/config"
      if [ -f "$cfg" ]; then
        printf '%s\n' "$cfg"
        return 0
      fi
      ;;
    esac
  fi
  return 1
}

remote_names_for_root_checkout() {
  local root_checkout="$1"
  [ -n "$root_checkout" ] || return 1
  local cfg
  cfg="$(git_config_file_for_worktree_root "$root_checkout" 2>/dev/null || true)"
  [ -n "$cfg" ] && [ -f "$cfg" ] || return 1
  awk 'match($0, /^\[remote \"([^\"]+)\"\]/, m) { print m[1] }' "$cfg" 2>/dev/null || true
}

parse_owner_from_remote_url() {
  local url="$1"
  local path=""

  url="${url%.git}"
  case "$url" in
  git@*:*/*)
    path="${url#git@*:}"
    ;;
  ssh://git@*/*/*)
    path="${url#ssh://git@*/}"
    ;;
  https://*/*/*)
    path="${url#https://*/}"
    ;;
  http://*/*/*)
    path="${url#http://*/}"
    ;;
  *)
    return 1
    ;;
  esac

  if [[ "$path" != */* ]]; then
    return 1
  fi

  printf '%s\n' "${path%%/*}"
}

remote_owner_for_root_checkout() {
  local root_checkout="$1"
  local remote_name="$2"
  [ -n "$root_checkout" ] || return 1
  [ -n "$remote_name" ] || return 1

  local cfg remote_url
  cfg="$(git_config_file_for_worktree_root "$root_checkout" 2>/dev/null || true)"
  [ -n "$cfg" ] && [ -f "$cfg" ] || return 1

  remote_url="$(
    awk -v remote="$remote_name" '
      BEGIN { section="" }
      match($0, /^\[remote \"([^\"]+)\"\]/, m) { section=m[1]; next }
      section == remote && match($0, /^[[:space:]]*url[[:space:]]*=[[:space:]]*(.+)$/, m) { print m[1]; exit }
    ' "$cfg" 2>/dev/null || true
  )"
  [ -n "$remote_url" ] || return 1

  parse_owner_from_remote_url "$remote_url"
}

first_party_owner_for_root_checkout() {
  local root_checkout="$1"
  local owner=""

  owner="$(remote_owner_for_root_checkout "$root_checkout" origin 2>/dev/null || true)"
  if [ -n "$owner" ]; then
    printf '%s\n' "$owner"
    return 0
  fi

  owner="$(remote_owner_for_root_checkout "$root_checkout" upstream 2>/dev/null || true)"
  if [ -n "$owner" ]; then
    printf '%s\n' "$owner"
    return 0
  fi

  return 1
}

self_login_hint() {
  local login
  login="$(tmux_opt '@pick_session_github_login' '')"
  if [ -z "$login" ]; then
    login="${GITHUB_USER:-${USER:-}}"
  fi
  printf '%s\n' "$login"
}

worktree_root_dir_for_path() {
  local p="$1"
  [ -n "$p" ] || return 1
  p="$(resolve_path "$p")"
  if [ -f "$p" ]; then
    p="$(dirname "$p")"
  fi
  [ -d "$p" ] || return 1

  local common common_path
  common="$(git -C "$p" rev-parse --git-common-dir 2>/dev/null || true)"
  [ -n "$common" ] || return 1
  case "$common" in
  /*) common_path="$common" ;;
  *) common_path="$p/$common" ;;
  esac
  common_path="$(resolve_path "$common_path")"
  if [ "$(basename "$common_path")" = ".git" ]; then
    dirname "$common_path"
  else
    printf '%s\n' "$common_path"
  fi
}

has_linked_worktrees_for_root_checkout() {
  local root_checkout="$1"
  [ -n "$root_checkout" ] || return 1
  root_checkout="$(resolve_path "$root_checkout")"
  local wt_dir="$root_checkout/.git/worktrees"
  [ -d "$wt_dir" ] || return 1
  find "$wt_dir" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null | grep -q .
}

default_branch_for_root_checkout() {
  local root_checkout="$1"
  [ -n "$root_checkout" ] || return 1
  root_checkout="$(resolve_path "$root_checkout")"
  [ -d "$root_checkout" ] || return 1

  local out remote branch cand
  for remote in origin upstream; do
    out="$(git -C "$root_checkout" symbolic-ref --quiet --short "refs/remotes/$remote/HEAD" 2>/dev/null || true)"
    [ -n "$out" ] || continue
    case "$out" in
    "$remote"/*) branch="${out#"$remote"/}" ;;
    */*) branch="${out#*/}" ;;
    *) branch="$out" ;;
    esac
    case "${branch,,}" in
    ".invalid" | "invalid" | "(invalid)" | "") ;;
    *)
      printf '%s\n' "$branch"
      return 0
      ;;
    esac
  done

  for cand in main master trunk develop dev; do
    if git -C "$root_checkout" show-ref --verify --quiet "refs/heads/$cand" 2>/dev/null ||
      git -C "$root_checkout" show-ref --verify --quiet "refs/remotes/origin/$cand" 2>/dev/null ||
      git -C "$root_checkout" show-ref --verify --quiet "refs/remotes/upstream/$cand" 2>/dev/null; then
      printf '%s\n' "$cand"
      return 0
    fi
  done
  printf 'main\n'
  return 0
}

is_default_branch_dir() {
  case "${1-}" in
  main | master | trunk | develop | dev) return 0 ;;
  esac
  return 1
}

is_exact_scan_root() {
  local p="$1"
  [ -n "$p" ] || return 1
  p="$(resolve_path "$p")"
  local r
  while IFS= read -r r; do
    [ -n "$r" ] || continue
    if [ "$p" = "$r" ]; then
      return 0
    fi
  done < <(scan_roots_list)
  return 1
}

find_wrapper_root_checkout_for_path() {
  local p="$1"
  [ -n "$p" ] || return 1
  p="$(resolve_path "$p")"
  if [ -f "$p" ]; then
    p="$(dirname "$p")"
  fi
  [ -d "$p" ] || return 1

  local cur="$p"
  local i=0
  local b cand
  while [ -n "$cur" ] && [ "$cur" != "/" ] && [ $i -lt 12 ]; do
    if ! is_exact_scan_root "$cur"; then
      for b in main master trunk develop dev; do
        cand="$cur/$b"
        if [ -d "$cand" ] && [ -e "$cand/.git" ]; then
          printf '%s\n' "$(resolve_path "$cand")"
          return 0
        fi
      done
    fi
    cur="$(dirname "$cur")"
    i="$((i + 1))"
  done
  return 1
}

branch_from_wrapper_path() {
  local root_checkout="$1"
  local wt_path="$2"
  [ -n "$root_checkout" ] || return 1
  [ -n "$wt_path" ] || return 1

  root_checkout="$(resolve_path "$root_checkout")"
  wt_path="$(resolve_path "$wt_path")"
  local wrapper rel first rest
  wrapper="$(resolve_path "$(dirname "$root_checkout")")"
  case "$wt_path" in
  "$wrapper" | "$wrapper"/*) ;;
  *) return 1 ;;
  esac
  rel="${wt_path#"$wrapper"/}"
  rel="${rel#/}"
  rel="${rel#./}"
  rel="${rel%/}"
  [ -n "$rel" ] || return 1

  if [[ "$rel" == */* ]]; then
    first="${rel%%/*}"
    rest="${rel#*/}"
    if [ -n "$first" ] && [ -n "$rest" ]; then
      case "$first" in
      origin | upstream) ;;
      *)
        has_remote=0
        while IFS= read -r r; do
          [ -n "$r" ] || continue
          if [ "$r" = "$first" ]; then
            has_remote=1
            break
          fi
        done < <(remote_names_for_root_checkout "$root_checkout" 2>/dev/null || true)
        if [ "${has_remote:-0}" -eq 1 ]; then
          local first_owner first_party_owner self_login
          first_owner="$(remote_owner_for_root_checkout "$root_checkout" "$first" 2>/dev/null || true)"
          first_party_owner="$(first_party_owner_for_root_checkout "$root_checkout" 2>/dev/null || true)"
          self_login="$(self_login_hint)"
          if [ -n "$first_owner" ]; then
            if [ -n "$first_party_owner" ] && [ "$first_owner" = "$first_party_owner" ]; then
              printf '%s\n' "$rest"
              return 0
            fi
            if [ -n "$self_login" ] && [ "$first_owner" = "$self_login" ]; then
              printf '%s\n' "$rest"
              return 0
            fi
          fi
          printf '%s\n' "${first}__${rest}"
          return 0
        fi
        ;;
      esac
    fi
  fi

  printf '%s\n' "$rel"
}

scan_roots_list() {
  local roots_raw root
  roots_raw="$(tmux_opt '@pick_session_worktree_scan_roots' "$HOME/work,$HOME/code,$HOME/.backport/repositories,$HOME/.local/share")"
  IFS=',' read -r -a roots <<<"$roots_raw"
  for root in "${roots[@]}"; do
    root="${root#"${root%%[![:space:]]*}"}"
    root="${root%"${root##*[![:space:]]}"}"
    [ -n "$root" ] || continue
    case "$root" in
    "~") root="$HOME" ;;
    "~/"*) root="$HOME/${root#~/}" ;;
    esac
    printf '%s\n' "$(resolve_path "$root")"
  done
}

scan_root_rank_for_path() {
  local p="$1"
  [ -n "$p" ] || {
    printf '999\n'
    return 0
  }
  p="$(resolve_path "$p")"
  local i=0 r
  while IFS= read -r r; do
    [ -n "$r" ] || continue
    case "$p" in
    "$r" | "$r"/*)
      printf '%s\n' "$i"
      return 0
      ;;
    esac
    i="$((i + 1))"
  done < <(scan_roots_list)
  printf '999\n'
}

top_segment_for_path() {
  local p="$1"
  p="$(resolve_path "$p")"
  case "$p" in
  "$HOME"/*)
    rel="${p#"$HOME"/}"
    top="${rel%%/*}"
    top="${top#.}"
    top="$(printf '%s\n' "$top" | normalize)"
    [ -n "$top" ] || top="home"
    printf '%s\n' "$top"
    ;;
  *)
    printf '%s\n' "$(printf '%s\n' "$(basename "$p")" | normalize)"
    ;;
  esac
}

unique_session_name_for_root() {
  local base="$1"
  local root="$2"
  local suffix candidate n
  suffix="$(top_segment_for_path "$root")"
  [ -n "$suffix" ] || suffix="alt"
  candidate="${base}@${suffix}"
  if ! tmux_has_session_exact "$candidate"; then
    printf '%s\n' "$candidate"
    return 0
  fi
  n=2
  while [ "$n" -le 50 ]; do
    candidate="${base}@${suffix}${n}"
    if ! tmux_has_session_exact "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
    n="$((n + 1))"
  done
  printf '%s\n' "${base}@${suffix}-$(date +%s)"
}

tmux_session_path() {
  local sess="$1"
  if [ "${__sess_cache_loaded:-0}" -eq 1 ]; then
    sess_path_for_name "$sess" 2>/dev/null || true
    return 0
  fi
  tmux display-message -p -t "$sess" '#{session_path}' 2>/dev/null || true
}

find_disambiguated_session_for_root() {
  local canonical="$1"
  local root="$2"
  [ -n "$canonical" ] || return 1
  [ -n "$root" ] || return 1
  root="$(resolve_path "$root")"

  local i name spath sr
  for i in "${!sess_names[@]}"; do
    name="${sess_names[$i]}"
    spath="${sess_paths[$i]}"
    [ -n "$name" ] || continue
    [ -n "$spath" ] || continue
    case "$name" in
    "${canonical}"@*) ;;
    *) continue ;;
    esac
    sr="$(worktree_root_dir_for_path "$spath" 2>/dev/null || true)"
    [ -n "$sr" ] || sr="$spath"
    sr="$(resolve_path "$sr")"
    if [ "$sr" = "$root" ]; then
      printf '%s\n' "$name"
      return 0
    fi
  done

  return 1
}

remove_paths_in_background() {
  local start_dir="$1"
  shift
  local -a paths=("$@")
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
AUTO_RENAME_SESSIONS="$(tmux_opt "@pick_session_auto_rename_sessions" "off")"

selection_count="$(printf '%s\n' "$selections" | awk 'NF { c++ } END { print c + 0 }')"
# Session creation should feel instant. Always create new sessions in a
# lightweight placeholder mode, then let the session-switch hook respawn panes
# into the real shell + layout when you actually enter the session.
create_layout="deferred"
created_any_session=0
target_session=""
primary_set=0
while IFS= read -r _line; do
  [ -n "$_line" ] || continue
  IFS=$'\t' read -r _disp kind path meta target _mk <<<"$_line"

  is_primary=0
  if [ -n "${primary_kind:-}" ] && [ -n "${primary_path:-}" ]; then
    if [ "$kind" = "$primary_kind" ] && [ "$path" = "$primary_path" ]; then
      if [ -z "${primary_target:-}" ] || [ "$target" = "$primary_target" ]; then
        is_primary=1
      fi
    fi
  fi

  case "$kind" in
  session)
    this_session="$target"
    # If this session was discovered via a worktree and it has a preferred name,
    # rename it on selection so the tmux session list matches the picker.
    case "$meta" in
    sess_root:* | sess_wt:*)
      if [[ "$meta" == *"|expected="* ]]; then
        expected="${meta#*|expected=}"
        expected="$(tmux_sanitize_session_name "$expected" 2>/dev/null || printf '%s' "$expected")"
        if [ -n "$expected" ] && [ "$expected" != "$this_session" ]; then
          if ! tmux_has_session_exact "$expected"; then
            tmux rename-session -t "$this_session" "$expected" 2>/dev/null || true
            if [ "${__sess_cache_loaded:-0}" -eq 1 ]; then
              sess_rename "$this_session" "$expected" || true
            fi
            this_session="$expected"
          fi
        fi
      fi
      ;;
    esac
    if ! tmux_has_session_exact "$this_session"; then
      if [ -n "$path" ] && [ -d "$path" ]; then
        ensure_session_layout "$this_session" "$path" "$create_layout"
      fi
    fi
    if [ "$is_primary" -eq 1 ] || [ "$primary_set" -eq 0 ]; then
      target_session="$this_session"
      [ "$is_primary" -eq 1 ] && primary_set=1
    fi
    ;;
  worktree)
    [ -n "$path" ] || continue
    [ -d "$path" ] || continue
    if [ "${__sess_cache_loaded:-0}" -ne 1 ]; then
      sess_cache_load
    fi
    branch=""
    case "$meta" in
    wt_root:* | wt:*)
      branch="${meta#wt_root:}"
      branch="${branch#wt:}"
      branch="${branch%%|*}"
      ;;
    esac
    repo_id=""
    if [[ "$meta" == *"|repo="* ]]; then
      repo_id="${meta#*|repo=}"
      repo_id="${repo_id%%|*}"
    fi
    if [ -z "$repo_id" ]; then
      # Fallback: use the worktree root path as a repo identifier.
      case "$path" in
      "$HOME"/*) repo_id="${path#"$HOME"/}" ;;
      *) repo_id="$path" ;;
      esac
    fi
    repo_id="$(tmux_sanitize_session_name "$repo_id" 2>/dev/null || printf '%s' "$repo_id")"
    session_name=""
    wt_root="$target"
    if [ -z "$wt_root" ]; then
      wt_root="$(worktree_root_dir_for_path "$path" 2>/dev/null || true)"
    fi
    [ -n "$wt_root" ] || wt_root="$path"
    if [ -z "$branch" ] && ! has_linked_worktrees_for_root_checkout "$wt_root"; then
      branch="$(default_branch_for_root_checkout "$wt_root" 2>/dev/null || true)"
    fi
    case "${branch,,}" in
    ".invalid" | "invalid" | "(invalid)") branch="" ;;
    esac
    branch="$(tmux_sanitize_session_name "$branch" 2>/dev/null || printf '%s' "$branch")"
    if [ -n "$branch" ] && [ -n "$repo_id" ]; then
      session_name="${repo_id}|${branch}"
    elif [ -n "$repo_id" ]; then
      session_name="$repo_id"
    elif [ -n "$branch" ]; then
      session_name="$branch"
    else
      session_name="$(basename "$path")"
    fi
    session_name="$(tmux_sanitize_session_name "$session_name" 2>/dev/null || printf '%s' "$session_name")"

    # If there is already a session pointing at this worktree path but it has a
    # different (often incomplete) name, rename it to the final chosen name so
    # panes/windows are preserved and the picker entry is consistent.
    if [ -n "$session_name" ] && ! tmux_has_session_exact "$session_name"; then
      rp_sel="$(resolve_path "$path")"
      sname_at_path="$(sess_name_for_rpath "$rp_sel" 2>/dev/null || true)"
      if [ -n "$sname_at_path" ] && [ "$sname_at_path" != "$session_name" ] && ! tmux_has_session_exact "$session_name"; then
        tmux rename-session -t "=${sname_at_path}" "$session_name" 2>/dev/null || true
        if [ "${__sess_cache_loaded:-0}" -eq 1 ]; then
          sess_rename "$sname_at_path" "$session_name" || true
        fi
      fi
    fi
    ensure_session_layout "$session_name" "$path" "$create_layout"
    if [ "$is_primary" -eq 1 ] || [ "$primary_set" -eq 0 ]; then
      target_session="$session_name"
      [ "$is_primary" -eq 1 ] && primary_set=1
    fi
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
    session="$(session_name --"${MODE}" "${dir_with_tilde}" 2>/dev/null || true)"
    if [ -z "$session" ]; then
      die "tmux: invalid @pick_session_mode: ${MODE}"
    fi
    session="$(tmux_sanitize_session_name "$session" 2>/dev/null || printf '%s' "$session")"
    ensure_session_layout "$session" "$path" "$create_layout"
    if [ "$is_primary" -eq 1 ] || [ "$primary_set" -eq 0 ]; then
      target_session="$session"
      [ "$is_primary" -eq 1 ] && primary_set=1
    fi
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
if ! tmux switch-client -t "=${target_session}" 2>/dev/null; then
  die "tmux: failed to switch to: ${target_session}"
fi

# If we created any new sessions, refresh the cache quickly so the next picker
# open shows them in their "true" group/position without waiting for TTL.
if [ "${created_any_session:-0}" -eq 1 ]; then
  tmux run-shell -b "$HOME/.config/tmux/scripts/pick_session/index_update.sh --force --quiet --quick-only" 2>/dev/null || true
fi
