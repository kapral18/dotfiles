#!/usr/bin/env bash
# Re-exec under a modern bash when macOS ships bash 3.2 as /bin/bash.
if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
  for _b in /opt/homebrew/bin/bash /usr/local/bin/bash; do
    [ -x "$_b" ] && exec "$_b" "$0" "$@"
  done
  exit 1
fi
set -euo pipefail

# shellcheck source=../lib/herdr_ws.sh
. "$HOME/.config/herdr/scripts/pickers/lib/herdr_ws.sh"

die() {
  picker_notify "$1"
  exit 0
}

need_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" > /dev/null 2>&1; then
    die "session picker: missing command: ${cmd}"
  fi
}

# shellcheck source=lib/session_naming.sh
. "$HOME/.config/herdr/scripts/pickers/session/lib/session_naming.sh"

need_cmd fzf
need_cmd herdr
need_cmd jq

if [[ -z "${HERDR_SOCKET_PATH:-}" ]]; then
  die "session picker: not running inside herdr"
fi

handoff_namespace_cmd="$HOME/.config/herdr/scripts/pickers/lib/handoff_namespace.py"
[ -x "$handoff_namespace_cmd" ] || die "session picker: missing script: $handoff_namespace_cmd"
handoff_token="${PICKER_HANDOFF_TOKEN:-}"
handoff_namespace_owned=0
if [ -z "$handoff_token" ]; then
  handoff_token="$("$handoff_namespace_cmd" begin --owner-pid "$$" --owner-role standalone-picker --entry session-picker 2> /dev/null || true)"
  [ -n "$handoff_token" ] || die "session picker: failed to initialize handoff namespace"
  handoff_namespace_owned=1
fi
export PICKER_HANDOFF_TOKEN="$handoff_token"
handoff_slot_path() {
  local slot="$1"
  local path=""
  path="$("$handoff_namespace_cmd" path "$slot" --token "$handoff_token" 2> /dev/null || true)"
  [ -n "$path" ] || die "session picker: failed to resolve handoff slot: $slot"
  printf '%s\n' "$path"
}

fzf_shell="$(command -v bash 2> /dev/null || printf '%s' '/usr/bin/env bash')"

bulk_guard_file="${XDG_CACHE_HOME:-$HOME/.cache}/herdr-pickers/pick_session_bulk_create.$$"
bulk_guard_set() {
  mkdir -p "${bulk_guard_file%/*}" && : > "$bulk_guard_file"
}
bulk_guard_clear() {
  rm -f "$bulk_guard_file"
}
bulk_guard_set
_pick_session_pid_scoped_files=()
_pick_session_cleanup_pid_scoped() {
  local _f
  for _f in "${_pick_session_pid_scoped_files[@]+"${_pick_session_pid_scoped_files[@]}"}"; do
    [ -n "$_f" ] || continue
    rm -f "$_f" 2> /dev/null || true
  done
}
_pick_session_cleanup_done=0
_pick_session_cleanup_all() {
  [ "${_pick_session_cleanup_done:-0}" -eq 0 ] || return 0
  _pick_session_cleanup_done=1
  bulk_guard_clear
  pkill -P $$ 2> /dev/null || true
  rm -f "${sort_daemon_sock:-}" 2> /dev/null || true
  _pick_session_cleanup_pid_scoped
  if [ "${handoff_namespace_owned:-0}" -eq 1 ] && [ -n "${handoff_token:-}" ]; then
    "$handoff_namespace_cmd" end --owner-pid "$$" --token "$handoff_token" > /dev/null 2>&1 || true
  fi
}
trap '_pick_session_cleanup_all; exit 0' INT HUP TERM
trap _pick_session_cleanup_all EXIT

__sess_cache_loaded=0
sess_names=()
sess_paths=()
sess_rpaths=()

sess_cache_load() {
  local out n p rp
  out="$(hws_list)"
  sess_names=()
  sess_paths=()
  sess_rpaths=()
  while IFS=$'\t' read -r n p; do
    [ -n "$n" ] || continue
    rp=""
    if [ -n "$p" ]; then
      rp="$(resolve_path "$p" 2> /dev/null || printf '%s' "$p")"
    fi
    sess_names+=("$n")
    sess_paths+=("$p")
    sess_rpaths+=("$rp")
  done <<< "$out"
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
  sess_index_for_name "$name" > /dev/null 2>&1
}

sess_path_for_name() {
  local name="$1"
  local i
  i="$(sess_index_for_name "$name" 2> /dev/null || true)"
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
  sess_rpaths+=("$(resolve_path "$path" 2> /dev/null || printf '%s' "$path")")
}

sess_rename() {
  local old="$1"
  local new="$2"
  [ -n "$old" ] || return 1
  [ -n "$new" ] || return 1
  local i
  i="$(sess_index_for_name "$old" 2> /dev/null || true)"
  [ -n "$i" ] || return 1
  sess_names[$i]="$new"
}

session_exists() {
  local name="$1"
  [ -n "$name" ] || return 1
  if [ "${__sess_cache_loaded:-0}" -eq 1 ]; then
    sess_has_name "$name"
    return $?
  fi
  hws_has "$name"
}

items_cmd="$HOME/.config/herdr/scripts/pickers/session/items.sh"
if [ ! -x "$items_cmd" ]; then
  die "session picker: missing script: $items_cmd"
fi

open_items_cmd="$HOME/.config/herdr/scripts/pickers/session/open_items.sh"
if [ ! -x "$open_items_cmd" ]; then
  open_items_cmd="$items_cmd"
fi

filter_cmd="$HOME/.config/herdr/scripts/pickers/session/filter.sh"
if [ ! -x "$filter_cmd" ]; then
  filter_cmd="$items_cmd"
fi

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/herdr-pickers"
mkdir -p "$cache_dir" 2> /dev/null || true
primary_tmp="${cache_dir}/pick_session_fzf_primary.$$.tsv"
_pick_session_pid_scoped_files+=("$primary_tmp")
pin_file="$(handoff_slot_path pick_session_pin)"
gh_pin_file="$(handoff_slot_path gh_picker_pin)"
switch_to_gh_file="$(handoff_slot_path pick_session_switch_gh)"
handoff_to_gh_cmd="$HOME/.config/herdr/scripts/pickers/lib/handoff_to_gh.sh"
pin_first_cmd="$HOME/.config/herdr/scripts/pickers/lib/pin_session_first.sh"

kill_cmd="$HOME/.config/herdr/scripts/pickers/session/action_kill_sessions.sh"
rm_cmd="$HOME/.config/herdr/scripts/pickers/session/action_remove_worktrees.sh"
altx_cmd="$HOME/.config/herdr/scripts/pickers/session/altx_remove_transform.sh"
if [ ! -x "$altx_cmd" ]; then
  die "session picker: missing script: $altx_cmd"
fi
live_refresh_cmd="$HOME/.config/herdr/scripts/pickers/session/live_refresh.sh"
hide_selected_cmd="$HOME/.config/herdr/scripts/pickers/session/items_hide_selected.sh"
update_cmd="$HOME/.config/herdr/scripts/pickers/session/index_update.sh"
dispatch_async_cmd="$HOME/.config/herdr/scripts/pickers/lib/dispatch_async.sh"

send_cmd="$HOME/.config/herdr/scripts/pickers/session/action_send_command.sh"
open_gh_cmd="$HOME/.config/herdr/scripts/pickers/session/action_open_gh.sh"
only_cycle_cmd="$HOME/.config/herdr/scripts/pickers/session/action_only_cycle.sh"
create_wt_cmd="$HOME/.config/herdr/scripts/pickers/session/action_create_worktree.sh"
cmd_tmp="${cache_dir}/pick_session_cmd.$$.txt"
mode_flag="${cache_dir}/pick_session_send_mode.$$"
wt_mode_flag="${cache_dir}/pick_session_wt_mode.$$"
wt_branch_tmp="${cache_dir}/pick_session_wt_branch.$$.txt"
only_mode_flag="${cache_dir}/pick_session_only_mode.$$"
rm -f "$only_mode_flag"
export PICK_SESSION_ONLY_FILE="$only_mode_flag"
rm_confirm_flag="${cache_dir}/pick_session_rm_confirm.$$"
rm_pending_snap="${cache_dir}/pick_session_rm_pending.$$.tsv"
# fzf SIGKILLs a still-running alt-x helper on exit, skipping its trap, so its
# markers are cleaned here too; a stale .busy would block alt-x and the modes.
_pick_session_pid_scoped_files+=("$cmd_tmp" "$mode_flag" "$wt_mode_flag" "$wt_branch_tmp" "$only_mode_flag" "$rm_confirm_flag" "${rm_confirm_flag}.busy" "${rm_confirm_flag}.run" "$rm_pending_snap")

filter_quick_1="$(picker_opt '@pick_session_filter_quick_1' 'code')"
filter_quick_2="$(picker_opt '@pick_session_filter_quick_2' 'share')"

fzf_args="$(picker_opt '@pick_session_fzf_options' '--no-sort')"
fzf_prompt="$(picker_opt '@pick_session_fzf_prompt' '󰍉  ')"
fzf_ghost="$(picker_opt '@pick_session_fzf_ghost' 'filter: repo, branch, path')"
fzf_color="$(picker_opt '@pick_session_fzf_color' 'prompt:111,query:223,input-bg:-1,input-fg:252,ghost:240,header:244,spinner:110,info:244,pointer:81,marker:214')"
fzf_ui_args=()
[ -n "$fzf_prompt" ] && fzf_ui_args+=(--prompt "$fzf_prompt")
[ -n "$fzf_ghost" ] && fzf_ui_args+=(--ghost "$fzf_ghost")
[ -n "$fzf_color" ] && fzf_ui_args+=(--color "$fzf_color")
query="$*"
pin_kind=""
pin_repo=""
pin_num=""
if [ -f "$pin_file" ]; then
  IFS=$'\t' read -r pin_kind pin_repo pin_num < "$pin_file" 2> /dev/null || true
  rm -f "$pin_file" 2> /dev/null || true
fi

help_cmd="$HOME/.config/herdr/scripts/pickers/session/keyhelp.sh"
preview_cmd="$HOME/.config/herdr/scripts/pickers/session/preview.sh"

help_flag="${cache_dir}/pick_session_help_flag.$$"
_pick_session_pid_scoped_files+=("$help_flag")
rm -f "$help_flag" 2> /dev/null || true

preview_cmd_0="$preview_cmd {f}"
preview_with_help="if [ -f $(printf %q "$help_flag") ]; then $(printf %q "$help_cmd"); else $(printf %q "$preview_cmd") {f}; fi"

# Relevance-rank matches without crossing kind tiers:
# - empty query: `--no-sort` preserves grouped/frecency ordering
# - non-empty query: sessions, worktrees, and directories remain strict tiers;
#   fzf relevance determines order only within each tier
sort_daemon_cmd="$HOME/.config/herdr/scripts/pickers/session/lib/sort_toggle_daemon.py"
sort_daemon_sock="${cache_dir}/pick_session_fzf.$$.sock"
sort_source_file="${cache_dir}/pick_session_fzf_source.$$.tsv"
sort_ranked_file="${cache_dir}/pick_session_fzf_ranked.$$.tsv"
_pick_session_pid_scoped_files+=("$sort_source_file" "$sort_ranked_file")
export PICK_SESSION_SORT_SOURCE_FILE="$sort_source_file"
rm -f "$sort_daemon_sock" "$sort_source_file" "$sort_ranked_file" 2> /dev/null || true
if command -v python3 > /dev/null 2>&1 && [ -r "$sort_daemon_cmd" ]; then
  python3 "$sort_daemon_cmd" "$sort_daemon_sock" "$sort_source_file" "$sort_ranked_file" > /dev/null 2>&1 &
  sort_daemon_pid=$!
else
  sort_daemon_pid=""
fi

snapshot_reload_command() {
  local command="$1"
  printf '{ %s | tee "${PICK_SESSION_SORT_SOURCE_FILE}.new.$$"; mv -f "${PICK_SESSION_SORT_SOURCE_FILE}.new.$$" "$PICK_SESSION_SORT_SOURCE_FILE"; }' "$command"
}
ctrl_r_reload="$(snapshot_reload_command "$filter_cmd --refresh --force-order")"
alt_r_reload="$(snapshot_reload_command "$filter_cmd --force-refresh --force-order")"
kill_reload="$(snapshot_reload_command "$hide_selected_cmd {+f} kill {q}")"

# The selection is captured at enter-time via `{+f}`, snapshotted by
# `dispatch_async.sh` running *inside* the enter:transform shell command. This
# placement matters: fzf substitutes `{+f}` into the transform body's shell
# command, runs it, then `removeFiles(tempFiles)` deletes the temp file (see
# `executeCommand` in fzf's terminal.go around line 5413/5507). If the dispatch
# were emitted inside the printed action string instead, the `{+f}` token there
# would already be a literal path that fzf had just deleted. Running
# `dispatch_async.sh` *during* the transform shell snapshots `{+f}` to a stable
# mktemp while the file is still alive, sidestepping that race.
_modal_header="$("$only_cycle_cmd" "$only_mode_flag" --header)"
_restore_header="transform-header($(printf %q "$only_cycle_cmd") $(printf %q "$only_mode_flag") --header)"
_modal_rebind='ctrl-s,ctrl-x,alt-x,alt-y,alt-c,alt-o,alt-p,alt-i,alt-g,change'
send_restore="enable-search+change-prompt($fzf_prompt)+change-ghost($fzf_ghost)+$_restore_header+clear-query+deselect-all+rebind($_modal_rebind)+unbind(esc)"

#   esc stays unbound outside modals: `start` unbinds it once, so reloads
#   (live refresh, re-sorting, ctrl-r) never touch it. The alt-x cue and the
#   force prompt rebind it, and every alt-x outcome (safe, force, restore)
#   unbinds it again. Without that, esc does nothing at the force prompt and
#   the next alt-x forces the pending blocked selection.
_altx_pending_q="$(printf %q "$rm_pending_snap")"
altx_src_q="$(printf %q "$sort_source_file")"
altx_visual_restore="change-prompt($fzf_prompt)+change-ghost($fzf_ghost)+$_restore_header+unbind(esc)"
altx_check_prompt='⏳ removing…'
altx_check_cue="change-prompt($altx_check_prompt)+rebind(esc)"
# fzf --ansi hands {+f} snapshots back color-stripped while the row source
# keeps its SGR codes, so the hide matches each source row's plain projection
# against the snapshot and prints survivors unchanged — rows keep their colors.
# FILENAME==ARGV[1] (not NR==FNR) so an empty snapshot still reads as
# "nothing selected" and never blanks the row set.
_altx_hide_awk='FILENAME==ARGV[1]{t=$0;gsub(/\033\[[0-9;]*m/,"",t);p[t]=1;next}{t=$0;gsub(/\033\[[0-9;]*m/,"",t);if(!(t in p))print}'
_altx_hide_matcher="LC_ALL=C awk $(printf %q "${_altx_hide_awk}")"
_altx_hide_reload="$(snapshot_reload_command "${_altx_hide_matcher} ${_altx_pending_q} ${altx_src_q}")"
altx_safe_actions="reload(${_altx_hide_reload})+deselect-all+${altx_visual_restore}"
altx_confirm_actions="change-prompt(❯ force: )+change-ghost(alt-x again = force  esc = cancel)+change-header(BLOCKED: unsaved work, submodules, or plain directory delete)+rebind(esc)"
altx_force_actions="reload(${_altx_hide_reload})+deselect-all+${altx_visual_restore}"
export ALTX_SAFE_ACTIONS="$altx_safe_actions"
export ALTX_CONFIRM_ACTIONS="$altx_confirm_actions"
export ALTX_FORCE_ACTIONS="$altx_force_actions"
export ALTX_RESTORE_ACTIONS="$altx_visual_restore"
send_mode="execute-silent(touch $mode_flag)+disable-search+change-prompt(❯ send: )+change-ghost()+change-header(enter=send  esc=cancel)+clear-query+unbind($_modal_rebind)+rebind(esc)"

wt_mode="execute-silent(touch $wt_mode_flag)+disable-search+change-prompt(❯ new branch: )+change-ghost(branch off selected repo)+change-header(enter=create worktree  esc=cancel)+clear-query+unbind($_modal_rebind)+rebind(esc)"

# A late alt-x outcome (safe, confirm, restore) would clobber a mode opened over
# it, and leaving a mode unbinds esc with a force prompt still armed. So send and
# new-branch modes open only while no alt-x check runs and no force is pending.
# The cue's prompt covers keys typed before the helper creates its .busy marker.
altx_pending="[ \"\$FZF_PROMPT\" = $(printf %q "$altx_check_prompt") ] || [ -e $(printf %q "${rm_confirm_flag}.busy") ] || [ -e $(printf %q "$rm_confirm_flag") ]"

enter_transform="enter:transform:if [ -f $mode_flag ]; then printf '%s' {q} > $cmd_tmp; $dispatch_async_cmd $send_cmd {+f} $cmd_tmp >/dev/null 2>&1; echo 'execute-silent(rm -f $mode_flag)+$send_restore'; elif [ -f $wt_mode_flag ]; then printf '%s' {q} > $wt_branch_tmp; $dispatch_async_cmd $create_wt_cmd {f} $wt_branch_tmp >/dev/null 2>&1; echo 'execute-silent(rm -f $wt_mode_flag)+$send_restore'; else echo 'execute-silent(cp {f} $primary_tmp)+accept'; fi"

fzf_common_binds=(
  --bind "start:execute-silent($live_refresh_cmd >/dev/null 2>&1 &)+unbind(esc)"
  --bind "ctrl-r:reload($ctrl_r_reload)+track"
  --bind "alt-r:reload($alt_r_reload)+track"
  --bind "alt-j:half-page-down"
  --bind "alt-k:half-page-up"
  --bind "alt-h:first"
  --bind "alt-l:last"
  --bind "shift-up:preview-up"
  --bind "shift-down:preview-down"
  --bind "shift-left:preview-page-up"
  --bind "shift-right:preview-page-down"
  --bind "ctrl-/:toggle-preview"
  --bind "?:execute-silent(if [ -f $(printf %q "$help_flag") ]; then rm -f $(printf %q "$help_flag"); else touch $(printf %q "$help_flag"); fi)+refresh-preview"
  --bind "change:first"
  --bind "alt-s:toggle-sort+first"
  --bind "$enter_transform"
  --bind "ctrl-s:transform:$altx_pending || printf '%s' $(printf %q "$send_mode")"
  --bind "esc:execute-silent(rm -f $mode_flag $wt_mode_flag $rm_confirm_flag ${rm_confirm_flag}.run)+$send_restore"
  --bind "ctrl-x:execute-silent($(printf %q "$dispatch_async_cmd") $(printf %q "$kill_cmd") {+f})+reload($kill_reload)+deselect-all"
  --bind "alt-x:${altx_check_cue}+bg-transform($(printf %q "$altx_cmd") $(printf %q "$rm_confirm_flag") $(printf %q "$rm_cmd") {+f} $(printf %q "$rm_pending_snap"))"
  --bind "alt-y:execute-silent(printf '%s\n' {+} | cut -f3 | sed '/^[[:space:]]*$/d' | pbcopy 2>/dev/null || printf '%s\n' {+} | cut -f3 | sed '/^[[:space:]]*$/d' | xclip -sel clip 2>/dev/null)"
  --bind "alt-Y:execute-silent(printf '%s\n' {+} | cut -f5 | sed '/^[[:space:]]*$/d' | pbcopy 2>/dev/null || printf '%s\n' {+} | cut -f5 | sed '/^[[:space:]]*$/d' | xclip -sel clip 2>/dev/null)"
  --bind "alt-1:change-query(${filter_quick_1}/)"
  --bind "alt-2:change-query(${filter_quick_2}/)"
  --bind "alt-o:transform($(printf %q "$only_cycle_cmd") $(printf %q "$only_mode_flag") $(printf %q "$filter_cmd"))"
  --bind "alt-c:transform:$altx_pending || printf '%s' $(printf %q "$wt_mode")"
  --bind "alt-p:execute-silent($open_gh_cmd pr {f})"
  --bind "alt-i:execute-silent($open_gh_cmd issue {f})"
  --bind "alt-g:execute-silent($(printf %q "$handoff_to_gh_cmd") {4} $(printf %q "$gh_pin_file") 2>/dev/null || true; touch $(printf %q "$switch_to_gh_file"))+abort"
  --header "$_modal_header"
)

fzf_base_args=(
  --with-shell "$fzf_shell -c"
  --ansi
  --scheme=path
  --height=100%
  --listen="$sort_daemon_sock"
  --filepath-word
  --reverse
  --tiebreak=begin,length,index
  --delimiter=$'\t'
  --id-nth=2,3
  --nth=1
  --with-nth=1
  --multi
  "${fzf_ui_args[@]}"
  --query "$query"
  --preview "$preview_with_help"
  --preview-window 'right,50%,border-left'
)

selection_file="${PICK_SESSION_SELECTION_FILE:-}"
if [ -n "$selection_file" ] && [ -f "$selection_file" ]; then
  pick="$(cat "$selection_file" 2> /dev/null || true)"
else
  rm -f "$primary_tmp" "$cmd_tmp" "$mode_flag" "$wt_mode_flag" "$only_mode_flag" 2> /dev/null || true
  # shellcheck disable=SC2086
  pick="$(
    if [ -n "$pin_kind" ] && [ -n "$pin_num" ] && [ -x "$pin_first_cmd" ]; then
      FZF_DEFAULT_OPTS="" "$open_items_cmd" | "$pin_first_cmd" "$pin_kind" "$pin_repo" "$pin_num" | tee "$sort_source_file" | SHELL="$fzf_shell" fzf \
        "${fzf_base_args[@]}" \
        "${fzf_common_binds[@]}" \
        ${fzf_args} \
        || true
    else
      FZF_DEFAULT_OPTS="" "$open_items_cmd" | tee "$sort_source_file" | SHELL="$fzf_shell" fzf \
        "${fzf_base_args[@]}" \
        "${fzf_common_binds[@]}" \
        ${fzf_args} \
        || true
    fi
  )"
fi

if [ -f "$switch_to_gh_file" ]; then
  exit 0
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
  primary_line="$(cat "$primary_tmp" 2> /dev/null | head -n 1 || true)"
  if [ -n "${primary_line:-}" ]; then
    picker_row_parse "$primary_line"
    primary_kind="${PICKER_ROW_FIELDS[1]-}"
    primary_path="${PICKER_ROW_FIELDS[2]-}"
    primary_target="${PICKER_ROW_FIELDS[4]-}"
  fi
fi

cache_session_lines=()
cache_session_line_add() {
  local name="$1"
  local dir="$2"
  local source_kind="${3:-}"
  [ -n "$name" ] || return 0
  [ -n "$dir" ] || return 0
  local line
  line="${name}"$'\t'"${dir}"$'\t'"${source_kind}"
  local existing
  for existing in "${cache_session_lines[@]+"${cache_session_lines[@]}"}"; do
    [ "$existing" = "$line" ] && return 0
  done
  cache_session_lines+=("$line")
}

record_session_cache_line() {
  local name="$1"
  local selected_dir="$2"
  local source_kind="${3:-}"
  [ -n "$name" ] || return 0
  [ -n "$selected_dir" ] || return 0
  local actual_dir selected_rp actual_rp
  actual_dir="$(session_path "$name" 2> /dev/null || true)"
  [ -n "$actual_dir" ] || actual_dir="$selected_dir"
  selected_rp="$(resolve_path "$selected_dir" 2> /dev/null || printf '%s' "$selected_dir")"
  actual_rp="$(resolve_path "$actual_dir" 2> /dev/null || printf '%s' "$actual_dir")"
  # If the requested name already belongs to a different path, do not make the
  # picker claim the selected folder is that session.
  [ "$selected_rp" = "$actual_rp" ] || return 0
  cache_session_line_add "$name" "$selected_dir" "$source_kind"
}

ensure_session_layout() {
  local name="$1"
  local dir="$2"
  local layout="${3:-split}"

  if session_exists "$name"; then
    return 0
  fi
  if ! _comma_w_create_workspace "$name" "$dir" "$layout" > /dev/null; then
    die "session picker: failed to create workspace: $name ($dir)"
  fi
  cache_session_line_add "$name" "$dir"
  if [ "${__sess_cache_loaded:-0}" -eq 1 ]; then
    sess_add "$name" "$dir" || true
  fi
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

scan_roots_list() {
  local roots_raw root
  roots_raw="$(picker_opt '@pick_session_worktree_scan_roots' "$HOME/code,$HOME/.local/share")"
  IFS=',' read -r -a roots <<< "$roots_raw"
  for root in "${roots[@]}"; do
    root="${root#"${root%%[![:space:]]*}"}"
    root="${root%"${root##*[![:space:]]}"}"
    [ -n "$root" ] || continue
    case "$root" in
      "~") root="$HOME" ;;
      "~/"*) root="$HOME/${root#\~/}" ;;
    esac
    printf '%s\n' "$(resolve_path "$root")"
  done
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
  if ! session_exists "$candidate"; then
    printf '%s\n' "$candidate"
    return 0
  fi
  n=2
  while [ "$n" -le 50 ]; do
    candidate="${base}@${suffix}${n}"
    if ! session_exists "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
    n="$((n + 1))"
  done
  printf '%s\n' "${base}@${suffix}-$(date +%s)"
}

session_path() {
  local sess="$1"
  if [ "${__sess_cache_loaded:-0}" -eq 1 ]; then
    sess_path_for_name "$sess" 2> /dev/null || true
    return 0
  fi
  hws_path "$sess"
}

# REPLY = the workspace to use for PATH: CANONICAL when free or already at PATH,
# else an existing workspace at PATH, else a suffixed variant of CANONICAL.
resolve_session_name_for_path() {
  local canonical="$1" path="$2"
  if [ "${__sess_cache_loaded:-0}" -ne 1 ]; then
    sess_cache_load
  fi
  local existing_path path_name
  if session_exists "$canonical"; then
    existing_path="$(session_path "$canonical")"
    if [ -z "$existing_path" ] || [ "$(resolve_path "$existing_path")" = "$(resolve_path "$path")" ]; then
      REPLY="$canonical"
      return 0
    fi
  fi
  path_name="$(sess_name_for_rpath "$(resolve_path "$path")" 2> /dev/null || true)"
  if [ -n "$path_name" ]; then
    REPLY="$path_name"
  elif session_exists "$canonical"; then
    REPLY="$(unique_session_name_for_root "$canonical" "$path")"
  else
    REPLY="$canonical"
  fi
}

MODE="$(picker_opt "@pick_session_mode" "directory")"

selection_count="$(printf '%s\n' "$selections" | awk 'NF { c++ } END { print c + 0 }')"
# One selection opens with two panes; bulk selections open one shell each so
# many concurrent prompts do not stall the machine.
if [ "$selection_count" -le 1 ]; then
  create_layout="split"
else
  create_layout=""
fi
target_session=""
primary_set=0
while IFS= read -r _line; do
  [ -n "$_line" ] || continue
  picker_row_parse "$_line"
  kind="${PICKER_ROW_FIELDS[1]-}"
  path="${PICKER_ROW_FIELDS[2]-}"
  meta="${PICKER_ROW_FIELDS[3]-}"
  target="${PICKER_ROW_FIELDS[4]-}"

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
      if ! session_exists "$this_session"; then
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
        case "$path" in
          "$HOME"/*) repo_id="${path#"$HOME"/}" ;;
          *) repo_id="$path" ;;
        esac
      fi
      repo_id="$(sanitize_session_name "$repo_id" 2> /dev/null || printf '%s' "$repo_id")"
      session_name=""
      wt_root="$target"
      if [ -z "$wt_root" ]; then
        wt_root="$(worktree_root_dir_for_path "$path" 2> /dev/null || true)"
      fi
      [ -n "$wt_root" ] || wt_root="$path"
      if [ -z "$branch" ] && ! has_linked_worktrees_for_root_checkout "$wt_root"; then
        branch="$(default_branch_for_root_checkout "$wt_root" 2> /dev/null || true)"
      fi
      case "${branch,,}" in
        ".invalid" | "invalid" | "(invalid)") branch="" ;;
      esac
      branch="$(sanitize_session_name "$branch" 2> /dev/null || printf '%s' "$branch")"
      if [ -n "$branch" ] && [ -n "$repo_id" ]; then
        session_name="${repo_id}|${branch}"
      elif [ -n "$repo_id" ]; then
        session_name="$repo_id"
      elif [ -n "$branch" ]; then
        session_name="$branch"
      else
        session_name="$(basename "$path")"
      fi
      session_name="$(sanitize_session_name "$session_name" 2> /dev/null || printf '%s' "$session_name")"

      resolve_session_name_for_path "$session_name" "$path"
      session_name="$REPLY"
      ensure_session_layout "$session_name" "$path" "$create_layout"
      record_session_cache_line "$session_name" "$path" "worktree"
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
      session="$(session_name --"${MODE}" "${dir_with_tilde}" 2> /dev/null || true)"
      if [ -z "$session" ]; then
        die "session picker: invalid @pick_session_mode: ${MODE}"
      fi
      session="$(sanitize_session_name "$session" 2> /dev/null || printf '%s' "$session")"
      resolve_session_name_for_path "$session" "$path"
      session="$REPLY"
      ensure_session_layout "$session" "$path" "$create_layout"
      record_session_cache_line "$session" "$path" "dir"
      if [ "$is_primary" -eq 1 ] || [ "$primary_set" -eq 0 ]; then
        target_session="$session"
        [ "$is_primary" -eq 1 ] && primary_set=1
      fi
      ;;
    *)
      continue
      ;;
  esac
done <<< "$selections"

if [ -z "$target_session" ]; then
  exit 0
fi

# Inject selected directory/worktree sessions into the cache before switching, so
# it happens within the bulk guard and the cache is ready before the user could reopen.
if [ "${#cache_session_lines[@]}" -gt 0 ]; then
  _cache_file="${cache_dir}/pick_session_items.tsv"
  _ordered_file="${cache_dir}/pick_session_items_ordered.tsv"
  _sess_icon=$'\033[38;5;42m\033[0m'
  _sess_color=$'\033[1;38;5;81m'
  _reset=$'\033[0m'
  for _csl in "${cache_session_lines[@]}"; do
    IFS=$'\t' read -r _cname _cpath _source_kind <<< "$_csl"
    [ -n "$_cname" ] || continue
    [ -n "$_cpath" ] || continue
    _label="$_cname"
    _mk="${_cname} ${_cpath}"
    if [ "$_source_kind" = "dir" ]; then
      tildefy_to_reply "$_cpath"
      _label="$REPLY"
      if is_exact_scan_root "$_cpath"; then
        _label="${_label}/"
      fi
      if [ "$_label" = "$_cpath" ]; then
        _mk="${_label} ${_cname}"
      else
        _mk="${_label} ${_cname} ${_cpath}"
      fi
    fi
    _row="${_sess_icon}  ${_sess_color}${_label}${_reset}"$'\t'"session"$'\t'"${_cpath}"$'\t'$'\t'"${_cname}"$'\t'"${_mk}"
    printf '%s\n' "$_row"
  done | python3 "$HOME/.config/herdr/scripts/pickers/lib/resource_lock.py" --timeout 0 inject-sessions "$_cache_file" || true
  rm -f "$_ordered_file" 2> /dev/null || true
  # Delay 1s so it doesn't compete with the initial shell render for CPU.
  "$HOME/lib/shared/detach.sh" bash -c 'sleep 1; exec "$1" --force --quiet --quick-only' _ "$update_cmd" < /dev/null > /dev/null 2>&1 &
fi

if ! hws_focus "$target_session"; then
  die "session picker: failed to focus: ${target_session}"
fi
