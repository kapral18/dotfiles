#!/usr/bin/env bash
# Picker view of herdr: a "session" is a workspace, identified by its label.

# shellcheck source=/dev/null
. "$HOME/lib/shared/worktree_lib.sh"

picker_notify() {
  herdr notification show picker --body "$1" > /dev/null 2>&1 || true
}

# Picker settings come from PICK_SESSION_* environment variables:
# picker_opt @pick_session_fzf_options '' reads PICK_SESSION_FZF_OPTIONS.
picker_opt() {
  local name="${1#@}"
  name="$(printf '%s' "$name" | tr '[:lower:]' '[:upper:]')"
  printf '%s\n' "${!name:-$2}"
}

# "<label>\t<path>" for every workspace.
hws_list() {
  _comma_w_workspace_list | cut -f1,2
}

# "<label>\t<path>\t<workspace_id>" for workspaces with a registered creation
# directory; the only rows destructive path matching may use. Close these by
# id: labels are not unique.
hws_list_registered() {
  _comma_w_workspace_list registered | cut -f1-3
}

hws_close_id() {
  herdr workspace close "$1" > /dev/null 2>&1
}

hws_has() {
  [ -n "$1" ] && [ -n "$(_comma_w_workspace_id_by_label "$1")" ]
}

hws_path() {
  _comma_w_workspace_list | awk -F'\t' -v l="$1" '$1 == l { print $2; exit }'
}

# Label of the workspace the picker was opened from.
hws_current() {
  local id="${HERDR_ACTIVE_WORKSPACE_ID:-${HERDR_WORKSPACE_ID:-}}"
  _comma_w_workspace_list | awk -F'\t' -v id="$id" '(id != "" && $3 == id) || (id == "" && $4 == "true") { print $1; exit }'
}

hws_close() {
  local id
  id="$(_comma_w_workspace_id_by_label "$1")"
  [ -z "$id" ] || herdr workspace close "$id" > /dev/null 2>&1
}

hws_focus() {
  local id
  id="$(_comma_w_workspace_id_by_label "$1")"
  [ -n "$id" ] && herdr workspace focus "$id" > /dev/null 2>&1
}

# Pane ids of workspace $1, in herdr's order.
hws_panes() {
  local id
  id="$(_comma_w_workspace_id_by_label "$1")"
  [ -n "$id" ] || return 1
  herdr pane list --workspace "$id" 2> /dev/null | jq -r '.result.panes[].pane_id'
}

# Foreground process name of pane $1 (the shell itself when idle).
hws_pane_command() {
  herdr pane process-info --pane "$1" 2> /dev/null \
    | jq -r '.result.process_info.foreground_processes | last | .name // empty' | sed 's/^-//'
}

# First pane of workspace $1 that sits at a shell prompt, else its first pane.
hws_shell_pane() {
  local pane first="" cmd
  while IFS= read -r pane; do
    [ -n "$pane" ] || continue
    [ -n "$first" ] || first="$pane"
    cmd="$(hws_pane_command "$pane")"
    case "$cmd" in
      fish | zsh | bash | sh)
        printf '%s\n' "$pane"
        return 0
        ;;
    esac
  done < <(hws_panes "$1" || true)
  [ -n "$first" ] && printf '%s\n' "$first"
}
