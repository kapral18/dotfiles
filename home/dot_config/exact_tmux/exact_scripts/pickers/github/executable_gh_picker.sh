#!/usr/bin/env bash
# fzf-based GitHub PR/issue picker.
# Native fzf GitHub integration that connects directly to ,w for worktree creation.
#
# Stale-while-revalidate: on open, cached items are shown instantly via
# start:reload(cache-only). A background process fetches fresh data and
# POSTs a reload to fzf's TCP listener once done. If the listener is
# unavailable (port collision, fzf already exited), the user still sees
# cached data and can ctrl-r to force refresh.
#
# Usage: gh_picker.sh [--mode work|home]
set -euo pipefail

trap 'exit 0' INT HUP TERM

die() {
  if [ -n "${TMUX:-}" ]; then
    tmux display-message "$1" 2> /dev/null || true
  fi
  printf '%s\n' "$1" >&2
  exit 0
}

for cmd in fzf gh yq python3; do
  command -v "$cmd" > /dev/null 2>&1 || die "gh-picker: missing $cmd"
done

mode="${GH_PICKER_MODE:-work}"
while [ $# -gt 0 ]; do
  case "$1" in
    --mode)
      mode="$2"
      shift 2
      ;;
    --mode=*)
      mode="${1#--mode=}"
      shift
      ;;
    *) shift ;;
  esac
done

script_dir="$(cd "$(dirname "$0")" && pwd)"
items_cmd="$script_dir/gh_items.sh"
preview_cmd="$script_dir/gh_preview.sh"
action_cmd="$script_dir/gh_action.sh"
comment_cmd="$script_dir/gh_comment.sh"
batch_wt_cmd="$script_dir/gh_batch_worktree.sh"
help_cmd="$script_dir/keyhelp.sh"
preview_warm_cmd="$script_dir/lib/gh_preview_warm.sh"

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
mkdir -p "$cache_dir" 2> /dev/null || true
primary_tmp="${cache_dir}/gh_picker_primary.tsv"
action_flag="${cache_dir}/gh_picker_action"
multi_tmp="${cache_dir}/gh_picker_multi.tsv"
expand_flag="${cache_dir}/gh_preview_expand"
help_flag="${cache_dir}/gh_picker_help"
port_file="${cache_dir}/gh_picker_port"
pin_file="${cache_dir}/gh_picker_pin"
pick_session_pin_file="${cache_dir}/pick_session_pin"
handoff_to_sessions_cmd="$HOME/.config/tmux/scripts/pickers/lib/handoff_to_sessions.sh"
handoff_to_ralph_cmd="$HOME/.config/tmux/scripts/pickers/lib/handoff_to_ralph_pin.sh"
pin_first_cmd="$HOME/.config/tmux/scripts/pickers/lib/pin_gh_first.sh"
ralph_pin_file="${cache_dir}/gh_picker_ralph_pin"

fzf_color="prompt:111,query:223,input-bg:-1,input-fg:252,ghost:240,header:244,spinner:110,info:244,pointer:81,marker:214"

mode_flag_file="${cache_dir}/gh_picker_mode"
printf '%s' "$mode" > "$mode_flag_file"

rm -f "$primary_tmp" "$action_flag" "$help_flag" "$multi_tmp" "$ralph_pin_file" 2> /dev/null || true
printf '0' > "$expand_flag"

toggle_cmd="$script_dir/lib/gh_picker_toggle.sh"

cache_load_cmd="GH_PICKER_MODE=$(printf %q "$mode") $(printf %q "$items_cmd") --cache-only"
full_load_cmd="GH_PICKER_MODE=$(printf %q "$mode") $(printf %q "$items_cmd")"

fzf_shell="$(command -v bash 2> /dev/null || printf '%s' /bin/bash)"

preview_with_help="if [ -f $(printf %q "$help_flag") ]; then $(printf %q "$help_cmd"); else m=\$(cat $(printf %q "$expand_flag") 2>/dev/null || echo 0); $(printf %q "$preview_cmd") --expand=\$m {f}; fi"

pin_kind=""
pin_repo=""
pin_num=""
if [ -f "$pin_file" ]; then
  IFS=$'\t' read -r pin_kind pin_repo pin_num < "$pin_file" 2> /dev/null || true
  rm -f "$pin_file" 2> /dev/null || true
fi

initial_items_cmd="$cache_load_cmd"
reload_items_cmd="$cache_load_cmd"
if [ -n "$pin_kind" ] && [ -n "$pin_repo" ] && [ -n "$pin_num" ] && [ -x "$pin_first_cmd" ]; then
  initial_items_cmd="$cache_load_cmd | $(printf %q "$pin_first_cmd") $(printf %q "$pin_kind") $(printf %q "$pin_repo") $(printf %q "$pin_num")"
  reload_items_cmd="$initial_items_cmd"
fi

items_cache="${cache_dir}/gh_picker_${mode}.tsv"

# Background fetch: launched from fzf's start binding where $FZF_PORT is available.
# Fetches fresh data from GitHub, then POSTs a reload to the running fzf instance.
# After reload, kicks off preview pre-warm for uncached items.
#
# Only POSTs the reload when the fetch actually succeeded. Otherwise (e.g. the
# fetch was killed by a concurrent ctrl-r refresh) the cache is still stale and
# telling fzf to reload from it would override an in-progress ctrl-r reload
# with the same stale content.
bg_fetch_cmd="($(printf %q "$preview_warm_cmd") $(printf %q "$items_cache") >/dev/null 2>&1 & sleep 0.15; if eval $(printf %q "$full_load_cmd") >/dev/null 2>&1; then printf '%s' \"\$FZF_PORT\" > $(printf %q "$port_file") 2>/dev/null || true; curl -s --max-time 5 -XPOST \"http://127.0.0.1:\${FZF_PORT}\" -d 'reload($reload_items_cmd)+track' 2>/dev/null || true; fi; $(printf %q "$preview_warm_cmd") $(printf %q "$items_cache") >/dev/null 2>&1 || true) &"

pick="$(
  eval "$initial_items_cmd" | SHELL="$fzf_shell" fzf \
    --with-shell "$fzf_shell -c" \
    --listen-unsafe \
    --ansi \
    --height=100% \
    --reverse \
    --multi \
    --delimiter=$'\t' \
    --nth=1,6 \
    --with-nth=1 \
    --marker '▌' \
    --prompt "  ${mode}  " \
    --ghost "filter PRs and issues" \
    --color "$fzf_color" \
    --preview "$preview_with_help" \
    --preview-window 'right,55%,border-left,wrap' \
    --header $'enter=checkout (batch if marked)  alt-A=ralph go  alt-b=octo  alt-o=browser  alt-y=copy url(s)  tab=mark  ctrl-s=work/home  alt-c=comment  ?=help' \
    --bind "start:execute-silent:$bg_fetch_cmd" \
    --bind "ctrl-r:reload(m=\$(cat $(printf %q "$mode_flag_file") 2>/dev/null || echo work); GH_PICKER_MODE=\$m $(printf %q "$items_cmd") --refresh)+track+clear-query" \
    --bind "ctrl-s:transform:$(printf %q "$toggle_cmd") $(printf %q "$mode_flag_file") $(printf %q "$items_cmd")" \
    --bind "alt-g:execute-silent($(printf %q "$handoff_to_sessions_cmd") {2} {3} {4} $(printf %q "$pick_session_pin_file") 2>/dev/null || true; touch ${cache_dir}/gh_picker_switch_sessions)+abort" \
    --bind "alt-A:execute-silent($(printf %q "$handoff_to_ralph_cmd") {2} {3} {4} {5} $(printf %q "$ralph_pin_file") 2>/dev/null || true)+abort" \
    --bind "alt-o:execute-silent($action_cmd open {2} {3} {4} {5})" \
    --bind "alt-y:execute-silent(printf '%s\n' {+} | cut -f5 | grep -E '^https?://' | pbcopy 2>/dev/null || printf '%s\n' {+} | cut -f5 | grep -E '^https?://' | xclip -sel clip 2>/dev/null)" \
    --bind "alt-space:toggle" \
    --bind "ctrl-t:execute(awk -F $'\\t' '\$2 != \"header\"' {+f} > $(printf %q "$multi_tmp"); $batch_wt_cmd $(printf %q "$multi_tmp"))+deselect-all+refresh-preview" \
    --bind "alt-e:execute-silent(m=\$(cat $(printf %q "$expand_flag") 2>/dev/null || echo 0); m=\$(( (m + 1) %% 3 )); printf '%s' \"\$m\" > $(printf %q "$expand_flag"))+refresh-preview" \
    --bind "alt-c:execute($comment_cmd new {2} {3} {4})+refresh-preview" \
    --bind "alt-r:execute($comment_cmd reply {2} {3} {4})+refresh-preview" \
    --bind "alt-d:execute($comment_cmd edit {2} {3} {4})+refresh-preview" \
    --bind "alt-j:half-page-down" \
    --bind "alt-k:half-page-up" \
    --bind "shift-up:preview-up" \
    --bind "shift-down:preview-down" \
    --bind "shift-left:preview-page-up" \
    --bind "shift-right:preview-page-down" \
    --bind "ctrl-/:toggle-preview" \
    --bind "?:execute-silent(if [ -f $(printf %q "$help_flag") ]; then rm -f $(printf %q "$help_flag"); else touch $(printf %q "$help_flag"); fi)+refresh-preview" \
    --bind "change:first" \
    --bind "enter:transform:if [ {2} = header ]; then echo 'down'; else echo 'accept'; fi" \
    --bind "alt-b:execute-silent(printf octo > $(printf %q "$action_flag"))+accept" \
    || true
)"

if [ -f "${cache_dir}/gh_picker_switch_sessions" ]; then
  exit 0
fi

[ -n "$pick" ] || exit 0

if [ ! -f "$primary_tmp" ]; then
  # Fallback: some fzf paths (or errors in execute bindings) may fail to copy {f}.
  # If fzf returned a selected line, use it directly.
  printf '%s\n' "$pick" | head -n 1 > "$primary_tmp" 2> /dev/null || exit 0
fi

line="$(head -n 1 "$primary_tmp" 2> /dev/null || true)"
[ -n "$line" ] || exit 0

kind="$(printf '%s' "$line" | awk -F $'\t' '{print $2}')"
repo="$(printf '%s' "$line" | awk -F $'\t' '{print $3}')"
num="$(printf '%s' "$line" | awk -F $'\t' '{print $4}')"
url="$(printf '%s' "$line" | awk -F $'\t' '{print $5}')"

selected_action="checkout"
if [ -f "$action_flag" ]; then
  selected_action="$(head -n 1 "$action_flag" 2> /dev/null || echo checkout)"
fi

case "$kind" in
  header)
    exit 0
    ;;
  pr | issue)
    "$action_cmd" "$selected_action" "$kind" "$repo" "$num" "$url"
    ;;
esac

rm -f "$primary_tmp" "$action_flag" "$expand_flag" "$help_flag" "$multi_tmp" 2> /dev/null || true
rm -f "$port_file" 2> /dev/null || true
