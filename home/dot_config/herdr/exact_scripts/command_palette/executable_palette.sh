#!/usr/bin/env bash
# Re-exec under a modern bash when macOS ships bash 3.2 as /bin/bash.
if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
  for _b in /opt/homebrew/bin/bash /usr/local/bin/bash; do
    [ -x "$_b" ] && exec "$_b" "$0" "$@"
  done
  exit 1
fi
set -euo pipefail

trap 'exit 0' INT HUP TERM

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/herdr-pickers"
HISTORY_FILE="${CACHE_DIR}/palette_history.tsv"
PALETTE_EXTRA_DIR="$HOME/.config/herdr/palette.d"
HERDR_CONFIG="${HERDR_CONFIG_PATH:-$HOME/.config/herdr/config.toml}"
BIN_DIR="$HOME/bin"

mkdir -p "$CACHE_DIR" 2> /dev/null || true

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

C_KIND=$'\033[38;5;244m'
C_CMD=$'\033[38;5;81m'
C_DESC=$'\033[38;5;252m'
C_KEY=$'\033[38;5;214m'
C_GIT=$'\033[38;5;150m'
C_R=$'\033[0m'

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

# One row per [[keys.command]] entry in herdr's config.toml.
emit_herdr_commands() {
  [ -f "$HERDR_CONFIG" ] || return 0
  awk -v kind="$C_KIND" -v ckey="$C_KEY" -v cdesc="$C_DESC" -v reset="$C_R" '
    function unq(v) {
      sub(/^[^=]*=[[:space:]]*/, "", v)
      if (v ~ /^"/) { v = substr(v, 2, length(v) - 2); gsub(/\\"/, "\"", v) }
      return v
    }
    function flush() {
      if (key != "" && cmd != "" && cmd !~ /command_palette/) {
        printf "%sherdr  %s⌘ %s  %s%s%s\t%s\t%s\n", kind, ckey, key, cdesc, (desc != "" ? desc : cmd), reset, "herdr:" type ":" key, cmd
      }
      key = ""; type = ""; cmd = ""; desc = ""
    }
    /^\[\[keys\.command\]\]/ { flush(); inblock = 1; next }
    /^\[/ { flush(); inblock = 0; next }
    inblock && /^key[[:space:]]*=/ { key = unq($0) }
    inblock && /^type[[:space:]]*=/ { type = unq($0) }
    inblock && /^command[[:space:]]*=/ { cmd = unq($0) }
    inblock && /^description[[:space:]]*=/ { desc = unq($0) }
    END { flush() }
  ' "$HERDR_CONFIG"
}

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

emit_palette_extras() {
  [ -d "$PALETTE_EXTRA_DIR" ] || return 0
  local f
  for f in "$PALETTE_EXTRA_DIR"/*.tsv; do
    [ -f "$f" ] || continue
    cat "$f"
  done
}

build_items() {
  {
    emit_bin_commands
    emit_herdr_commands
    emit_git_aliases
    emit_palette_extras
  } | recency_rank
}

preview_cmd() {
  local kind_key="$1"
  local exec_col="$2"

  case "$kind_key" in
    bin:*)
      local cmd_name="${kind_key#bin:}"
      local cmd_path="${BIN_DIR}/${cmd_name}"
      if [ -x "$cmd_path" ]; then
        printf 'Command: %s\n\n' "$cmd_name"
        head -40 "$cmd_path"
      fi
      ;;
    herdr:*)
      printf 'herdr binding: %s\n\n' "${kind_key##*:}"
      printf 'Command:\n  %s\n' "$exec_col"
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

type_into_pane() {
  [ -n "${HERDR_ACTIVE_PANE_ID:-}" ] || return 0
  herdr pane send-text "$HERDR_ACTIVE_PANE_ID" "$1" > /dev/null 2>&1 || true
}

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
        type_into_pane "$cmd_name "
      fi
      ;;
    herdr:plugin_action:*)
      herdr plugin action invoke "$exec_col" > /dev/null 2>&1 || true
      ;;
    herdr:*)
      # The palette already runs in a popup, so popup commands run here.
      [ -n "$exec_col" ] || return 0
      bash -c "$exec_col" || true
      ;;
    git:*)
      local alias_name="${kind_key#git:}"
      type_into_pane "git ${alias_name} "
      ;;
    *)
      [ -n "$exec_col" ] || return 0
      type_into_pane "$exec_col "
      ;;
  esac
}

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
