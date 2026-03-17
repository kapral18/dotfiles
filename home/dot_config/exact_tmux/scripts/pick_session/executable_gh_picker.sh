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

bg_pid=""
cleanup() {
  [ -n "$bg_pid" ] && kill "$bg_pid" 2> /dev/null || true
}
trap 'cleanup; exit 0' INT HUP TERM EXIT

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
handoff_to_sessions_cmd="$script_dir/handoff_to_sessions.sh"
pin_first_cmd="$script_dir/pin_gh_first.sh"

fzf_color="prompt:111,query:223,input-bg:-1,input-fg:252,ghost:240,header:244,spinner:110,info:244,pointer:81,marker:214"

mode_flag_file="${cache_dir}/gh_picker_mode"
printf '%s' "$mode" > "$mode_flag_file"

rm -f "$primary_tmp" "$action_flag" "$help_flag" "$multi_tmp" 2> /dev/null || true
printf '0' > "$expand_flag"

toggle_cmd="$script_dir/lib/gh_picker_toggle.sh"

cache_load_cmd="GH_PICKER_MODE=$(printf %q "$mode") $(printf %q "$items_cmd") --cache-only"
full_load_cmd="GH_PICKER_MODE=$(printf %q "$mode") $(printf %q "$items_cmd")"

fzf_port="$(python3 -c 'import socket; s=socket.socket(); s.bind(("",0)); print(s.getsockname()[1]); s.close()')"
printf '%s' "$fzf_port" > "$port_file" 2> /dev/null || true

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

(
  # Let the UI paint before doing heavier background fetches.
  sleep 0.15
  eval "$full_load_cmd" > /dev/null 2>&1 || true
  # Use IPv4 explicitly; on macOS `localhost` may resolve to ::1 while fzf binds 127.0.0.1.
  curl -s --max-time 5 -XPOST "http://127.0.0.1:${fzf_port}" \
    -d "reload($reload_items_cmd)+track" 2> /dev/null || true
) &
bg_pid=$!

pick="$(
  eval "$initial_items_cmd" | fzf \
    --listen-unsafe=$fzf_port \
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
    --preview "$preview_cmd --expand=\$(cat $(printf %q "$expand_flag") 2>/dev/null || echo 0) {f}" \
    --preview-window 'right,55%,border-left,wrap' \
    --header $'enter=checkout (batch if marked)  alt-b=octo  alt-o=browser  alt-y=copy  tab=mark  ctrl-s=work/home  alt-c=comment  ?=help' \
    --bind "ctrl-r:transform:m=\$(cat $(printf %q "$mode_flag_file")); echo \"reload(GH_PICKER_MODE=\$m $items_cmd --refresh)+clear-query\"" \
    --bind "ctrl-s:transform:$(printf %q "$toggle_cmd") $(printf %q "$mode_flag_file") $(printf %q "$items_cmd")" \
    --bind "alt-g:execute-silent($(printf %q "$handoff_to_sessions_cmd") {2} {3} {4} $(printf %q "$pick_session_pin_file") 2>/dev/null || true; touch ${cache_dir}/gh_picker_switch_sessions)+abort" \
    --bind "alt-o:execute-silent($action_cmd open {2} {3} {4} {5})" \
    --bind "alt-y:execute-silent(printf '%s' {5} | pbcopy 2>/dev/null || printf '%s' {5} | xclip -sel clip 2>/dev/null)" \
    --bind "alt-space:toggle" \
    --bind "ctrl-t:execute(cat {+f} > $(printf %q "$multi_tmp"); $batch_wt_cmd $(printf %q "$multi_tmp"))+deselect-all+refresh-preview" \
    --bind "alt-e:execute-silent(m=\$(cat $(printf %q "$expand_flag") 2>/dev/null || echo 0); m=\$(( (m + 1) %% 3 )); printf '%%s' \"\$m\" > $(printf %q "$expand_flag"))+refresh-preview" \
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
    --bind "?:transform:if [ -f $(printf %q "$help_flag") ]; then rm -f $(printf %q "$help_flag"); echo 'change-preview($preview_cmd --expand=\$(cat $(printf %q "$expand_flag") 2>/dev/null || echo 0) {f})+show-preview'; else touch $(printf %q "$help_flag"); echo 'change-preview(printf \"GitHub Picker Keybindings\n\nActions\nenter       checkout (batch if items marked)\nalt-b       checkout + Octo review (PRs)\nalt-o       open in browser\nalt-y       copy URL to clipboard\n\nMulti-select\ntab         mark/unmark item\nshift-tab   unmark item\nalt-space   mark/unmark item\n\nComments\nalt-c       new comment (opens \\\$EDITOR)\nalt-r       quote-reply a comment\nalt-d       edit your own comment\n\nPreview\nalt-e       cycle: collapsed → body → all expanded\nctrl-/      toggle preview\n\nNavigation\nctrl-s      switch work/home\nctrl-r      refresh from GitHub\nalt-g       switch to sessions picker\nalt-j/k     page down/up\nshift-↑/↓   scroll preview\n\")+show-preview'; fi" \
    --bind "focus:execute-silent(rm -f $(printf %q "$help_flag") 2>/dev/null)+change-preview($preview_cmd --expand=\$(cat $(printf %q "$expand_flag") 2>/dev/null || echo 0) {f})" \
    --bind "change:first" \
    --bind "enter:transform:[[ \$FZF_SELECT_COUNT -gt 0 ]] && echo 'execute(cat {+f} > $(printf %q "$multi_tmp"); $(printf %q "$batch_wt_cmd") $(printf %q "$multi_tmp"))+deselect-all+refresh-preview' || echo 'execute-silent(printf checkout > $(printf %q "$action_flag"))+execute-silent(cp {f} $(printf %q "$primary_tmp"))+accept'" \
    --bind "alt-b:execute-silent(printf octo > $(printf %q "$action_flag"))+execute-silent(cp {f} $(printf %q "$primary_tmp"))+accept" \
    || true
)"

if [ -f "${cache_dir}/gh_picker_switch_sessions" ]; then
  exit 0
fi

[ -n "$pick" ] || exit 0

if [ ! -f "$primary_tmp" ]; then
  exit 0
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
