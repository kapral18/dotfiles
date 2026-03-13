#!/usr/bin/env bash
# Re-exec under a modern bash when macOS ships bash 3.2 as /bin/bash.
if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
  _b="$(brew --prefix bash 2> /dev/null)/bin/bash"
  [ -x "$_b" ] && exec "$_b" "$0" "$@"
  exit 1
fi
set -euo pipefail

trap 'exit 0' INT HUP TERM

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
HISTORY_FILE="${CACHE_DIR}/palette_history.tsv"
PALETTE_EXTRA_DIR="$HOME/.config/tmux/palette.d"
BIN_DIR="$HOME/bin"

mkdir -p "$CACHE_DIR" 2> /dev/null || true

# ── recency helpers ──────────────────────────────────────────────────────────

touch_history() {
  local key="$1"
  [ -n "$key" ] || return 0
  local ts
  ts="$(date +%s)"
  local tmp="${HISTORY_FILE}.tmp.$$"
  {
    printf '%s\t%s\n' "$ts" "$key"
    if [ -f "$HISTORY_FILE" ]; then
      grep -v $'\t'"${key}$" "$HISTORY_FILE" 2> /dev/null | head -200 || true
    fi
  } > "$tmp"
  mv -f "$tmp" "$HISTORY_FILE"
}

recency_rank() {
  if [ ! -f "$HISTORY_FILE" ]; then
    cat
    return
  fi
  awk -F'\t' '
    NR == FNR { rank[FNR] = $NF; next }
    {
      key = $NF
      r = 999999
      for (i in rank) { if (rank[i] == key) { r = i; break } }
      printf "%06d\t%s\n", r, $0
    }
  ' "$HISTORY_FILE" - \
    | sort -t$'\t' -k1,1n \
    | cut -f2-
}

# ── ANSI helpers ─────────────────────────────────────────────────────────────

C_KIND=$'\033[38;5;244m'
C_CMD=$'\033[38;5;81m'
C_DESC=$'\033[38;5;252m'
C_KEY=$'\033[38;5;214m'
C_GIT=$'\033[38;5;150m'
C_R=$'\033[0m'

# ── source: ~/bin/,* commands ────────────────────────────────────────────────

emit_bin_commands() {
  local f name desc line
  for f in "$BIN_DIR"/,*; do
    [ -f "$f" ] && [ -x "$f" ] || continue
    name="${f##*/}"
    desc=""
    while IFS= read -r line; do
      case "$line" in
        "# Description: "*)
          desc="${line#"# Description: "}"
          break
          ;;
        '"""') break ;;
        "#!/"*) continue ;;
        "#!"*) continue ;;
        "") continue ;;
        "# "*) continue ;;
        *) break ;;
      esac
    done < "$f"
    [ -n "$desc" ] || desc="(run ${name})"
    printf '%s%s  %s%s  %s%s%s\t%s\t%s\n' \
      "$C_KIND" "cmd" "$C_CMD" "$name" "$C_DESC" "$desc" "$C_R" \
      "bin:${name}" "$name"
  done
}

# ── source: tmux prefix keybindings ──────────────────────────────────────────

human_key() {
  local raw="$1"
  case "$raw" in
    "C-@") printf 'C-Space' ;;
    "\"") printf '"' ;;
    "\\%") printf '%%' ;;
    "\\$") printf '$' ;;
    "\\#") printf '#' ;;
    "\\;") printf ';' ;;
    "\\'") printf "'" ;;
    *) printf '%s' "$raw" ;;
  esac
}

describe_tmux_action() {
  local action="$1"
  case "$action" in
    *pick_session/pick_session.sh*) printf 'Session picker' ;;
    *pick_session/popup.sh*) printf 'Session picker (popup)' ;;
    *command_palette*) printf 'Command palette' ;;
    *gh_dash/popup.sh*) printf 'GitHub dashboard (gh-dash)' ;;
    *gh_dash/restart.sh*) printf 'Restart gh-dash' ;;
    *gh_tfork/popup.sh*) printf 'Bootstrap repo (fork+clone)' ;;
    *pick_url.sh*) printf 'URL picker' ;;
    *promote_pane.sh*) printf 'Promote pane to session' ;;
    *promote_window.sh*) printf 'Promote window to session' ;;
    *new_session_prompt.sh*) printf 'New session (prompt)' ;;
    *kill_session_prompt.sh*) printf 'Kill session (prompt)' ;;
    *join_pane.sh*) printf 'Join pane' ;;
    *goto_session.sh*) printf 'Go to session' ;;
    *switch_or_loop.sh*) printf 'Switch or loop sessions' ;;
    *resurrect*save*) printf 'Save session state (resurrect)' ;;
    *resurrect*restore*) printf 'Restore session state (resurrect)' ;;
    *install_plugins*) printf 'Install tmux plugins (TPM)' ;;
    *clean_plugins*) printf 'Clean tmux plugins (TPM)' ;;
    *update_plugins*) printf 'Update tmux plugins (TPM)' ;;
    *tmux-lowfi*) printf 'Toggle lo-fi music' ;;
    "kill-window") printf 'Kill window' ;;
    "kill-pane") printf 'Kill pane' ;;
    "next-window") printf 'Next window' ;;
    "previous-window") printf 'Previous window' ;;
    "next-window -a") printf 'Next window (alert)' ;;
    "previous-window -a") printf 'Previous window (alert)' ;;
    "split-window -v"*) printf 'Split pane horizontal' ;;
    "split-window -h"*) printf 'Split pane vertical' ;;
    "resize-pane -Z") printf 'Toggle zoom' ;;
    "resize-pane -L"*) printf 'Resize pane left' ;;
    "resize-pane -R"*) printf 'Resize pane right' ;;
    "resize-pane -U"*) printf 'Resize pane up' ;;
    "resize-pane -D"*) printf 'Resize pane down' ;;
    "select-pane -L") printf 'Focus pane left' ;;
    "select-pane -R") printf 'Focus pane right' ;;
    "select-pane -U") printf 'Focus pane up' ;;
    "select-pane -D") printf 'Focus pane down' ;;
    "select-layout -E") printf 'Spread panes evenly' ;;
    "next-layout") printf 'Next layout' ;;
    "rotate-window") printf 'Rotate window' ;;
    "rotate-window -D") printf 'Rotate window (reverse)' ;;
    "last-pane") printf 'Last pane' ;;
    "last-window") printf 'Last window' ;;
    "switch-client -l") printf 'Last session' ;;
    "switch-client -n") printf 'Next session' ;;
    "switch-client -p") printf 'Previous session' ;;
    "switch-client -T k18") printf 'Swap mode (prefix s)' ;;
    "swap-pane -d -t -1") printf 'Swap pane left' ;;
    "swap-pane -d -t +1") printf 'Swap pane right' ;;
    "swap-window -d -t -1") printf 'Swap window left' ;;
    "swap-window -d -t +1") printf 'Swap window right' ;;
    "choose-buffer -Z") printf 'Choose paste buffer' ;;
    "choose-client -Z") printf 'Choose client' ;;
    "choose-tree -Zs") printf 'Choose session tree' ;;
    "choose-tree -Zw") printf 'Choose window tree' ;;
    "command-prompt") printf 'Command prompt' ;;
    "command-prompt -I"*"rename-session"*) printf 'Rename session' ;;
    "command-prompt -I"*"rename-window"*) printf 'Rename window' ;;
    "command-prompt -T target"*) printf 'Move window to target' ;;
    "command-prompt -T window-target"*) printf 'Select window by index' ;;
    "copy-mode") printf 'Enter copy mode' ;;
    "list-buffers") printf 'List buffers' ;;
    "list-keys -N") printf 'List keybindings' ;;
    "list-keys -1N"*) printf 'Describe key' ;;
    "display-panes") printf 'Display pane numbers' ;;
    "display-message"*) printf 'Display message' ;;
    "source-file"*) printf 'Reload tmux config' ;;
    "suspend-client") printf 'Suspend client' ;;
    "send-prefix") printf 'Send prefix' ;;
    "break-pane") printf 'Break pane to window' ;;
    "detach-client") printf 'Detach client' ;;
    "select-window -t"*) printf 'Select window %s' "${action##*:=}" ;;
    "refresh-client"*) printf 'Refresh client' ;;
    *) printf '%s' "$action" ;;
  esac
}

emit_tmux_bindings() {
  local table key action desc hk
  while IFS= read -r line; do
    table=""
    key=""
    action=""
    if [[ "$line" =~ ^bind-key[[:space:]]+-r?[[:space:]]+-T[[:space:]]+prefix[[:space:]]+([^[:space:]]+)[[:space:]]+(.+)$ ]]; then
      key="${BASH_REMATCH[1]}"
      action="${BASH_REMATCH[2]}"
    elif [[ "$line" =~ ^bind-key[[:space:]]+-T[[:space:]]+prefix[[:space:]]+([^[:space:]]+)[[:space:]]+(.+)$ ]]; then
      key="${BASH_REMATCH[1]}"
      action="${BASH_REMATCH[2]}"
    elif [[ "$line" =~ ^bind-key[[:space:]]+-T[[:space:]]+k18[[:space:]]+([^[:space:]]+)[[:space:]]+(.+)$ ]]; then
      key="s ${BASH_REMATCH[1]}"
      action="${BASH_REMATCH[2]}"
    else
      continue
    fi
    # Skip the palette's own binding to avoid recursion in the list.
    case "$action" in
      *command_palette*) continue ;;
    esac
    hk="$(human_key "$key")"
    desc="$(describe_tmux_action "$action")"
    printf '%s%s  %s⌘ %s  %s%s%s\t%s\t%s\n' \
      "$C_KIND" "tmux" "$C_KEY" "$hk" "$C_DESC" "$desc" "$C_R" \
      "tmux:${hk}" "$action"
  done < <(
    tmux list-keys -T prefix 2> /dev/null
    tmux list-keys -T k18 2> /dev/null
  )
}

# ── source: git aliases ─────────────────────────────────────────────────────

emit_git_aliases() {
  local alias_key name cmd
  while IFS= read -r line; do
    alias_key="${line%% *}"
    name="${alias_key#alias.}"
    cmd="${line#"$alias_key "}"
    [ -n "$name" ] || continue
    printf '%s%s  %s%s  %s%s%s\t%s\t%s\n' \
      "$C_KIND" " git" "$C_GIT" "git $name" "$C_DESC" "$cmd" "$C_R" \
      "git:${name}" "git $name"
  done < <(git config --global --get-regexp '^alias\.' 2> /dev/null || true)
}

# ── source: palette.d drop-ins ───────────────────────────────────────────────

emit_palette_extras() {
  [ -d "$PALETTE_EXTRA_DIR" ] || return 0
  local f
  for f in "$PALETTE_EXTRA_DIR"/*.tsv; do
    [ -f "$f" ] || continue
    cat "$f"
  done
}

# ── build the full list ──────────────────────────────────────────────────────

build_items() {
  {
    emit_bin_commands
    emit_tmux_bindings
    emit_git_aliases
    emit_palette_extras
  } | recency_rank
}

# ── preview: show help / details for the selected entry ──────────────────────

preview_cmd() {
  local kind_key="$1"
  local exec_col="$2"

  case "$kind_key" in
    bin:*)
      local cmd_name="${kind_key#bin:}"
      local cmd_path="${BIN_DIR}/${cmd_name}"
      if [ -x "$cmd_path" ]; then
        "$cmd_path" --help 2>&1 | head -40 || head -30 "$cmd_path"
      fi
      ;;
    tmux:*)
      printf 'Tmux binding: prefix + %s\n\n' "${kind_key#tmux:}"
      printf 'Action:\n  tmux %s\n' "$exec_col"
      ;;
    git:*)
      local alias_name="${kind_key#git:}"
      printf 'Git alias: %s\n\n' "$alias_name"
      git config --global --get "alias.${alias_name}" 2> /dev/null || true
      ;;
    *)
      printf '%s\n' "$exec_col"
      ;;
  esac
}

# ── execute the selected entry ───────────────────────────────────────────────

execute_entry() {
  local selected="$1"
  local exec_col kind_key
  exec_col="$(printf '%s' "$selected" | awk -F'\t' '{ print $NF }')"
  kind_key="$(printf '%s' "$selected" | awk -F'\t' '{ print $(NF-1) }')"

  touch_history "$kind_key"

  case "$kind_key" in
    bin:*)
      local cmd_name="${kind_key#bin:}"
      local cmd_path="${BIN_DIR}/${cmd_name}"
      if [ -x "$cmd_path" ]; then
        tmux send-keys "$cmd_name " 2> /dev/null || true
      fi
      ;;
    tmux:*)
      [ -n "$exec_col" ] || return 0
      eval "tmux $exec_col" 2> /dev/null || true
      ;;
    git:*)
      local alias_name="${kind_key#git:}"
      tmux send-keys "git ${alias_name} " 2> /dev/null || true
      ;;
    *)
      [ -n "$exec_col" ] || return 0
      tmux send-keys "$exec_col " 2> /dev/null || true
      ;;
  esac
}

# ── main ─────────────────────────────────────────────────────────────────────

if [ "${1:-}" = "--preview" ]; then
  preview_cmd "${2:-}" "${3:-}"
  exit 0
fi

SELF="$(realpath "$0" 2> /dev/null || printf '%s' "$0")"

selected="$(
  FZF_DEFAULT_OPTS="" build_items | fzf \
    --ansi \
    --scheme=default \
    --height=100% \
    --reverse \
    --delimiter=$'\t' \
    --nth=1 \
    --with-nth=1 \
    --tiebreak=index \
    --prompt '  ' \
    --ghost 'filter: session, git, brew, pr' \
    --color 'prompt:111,query:223,input-bg:-1,input-fg:252,ghost:240,header:244,spinner:110,info:244,pointer:81,marker:214' \
    --preview "\"$SELF\" --preview {2} {3}" \
    --preview-window 'right,40%,wrap,hidden,border-left' \
    --bind 'change:first' \
    --bind 'alt-j:half-page-down' \
    --bind 'alt-k:half-page-up' \
    --bind 'alt-h:first' \
    --bind 'alt-l:last' \
    --bind 'shift-up:preview-up' \
    --bind 'shift-down:preview-down' \
    --bind 'shift-left:preview-page-up' \
    --bind 'shift-right:preview-page-down' \
    --header $'enter=run  ctrl-/=preview  alt-h/l=jump' \
    --bind 'ctrl-/:toggle-preview' \
    || true
)"

[ -n "$selected" ] || exit 0

execute_entry "$selected"
