#!/usr/bin/env bash
# Move every pane of the active tab into a new workspace (tmux "promote
# window"), named after the tab when it has a name. herdr cannot move a whole
# tab, so the panes land side by side and focus goes to the first one.
set -euo pipefail

ws="${HERDR_ACTIVE_WORKSPACE_ID:-}"
tab="${HERDR_ACTIVE_TAB_ID:-}"
[ -n "$ws" ] && [ -n "$tab" ] || exit 0

notify() {
  herdr notification show "promote tab" --body "$1" > /dev/null 2>&1 || true
}

tabs="$(herdr tab list --workspace "$ws" | jq -r '.result.tabs | length')"
if [ "$tabs" -lt 2 ]; then
  notify "the workspace has only this tab"
  exit 0
fi

label="$(herdr tab get "$tab" | jq -r '.result.tab.label')"
label_args=()
case "$label" in
  '' | *[!0-9]*) [ -z "$label" ] || label_args=(--label "$label") ;;
  *) ;; # an unnamed tab reports its position; let herdr name the workspace
esac
panes=()
while IFS= read -r pane; do
  [ -n "$pane" ] && panes+=("$pane")
done < <(herdr pane list --workspace "$ws" | jq -r --arg tab "$tab" '.result.panes[] | select(.tab_id == $tab) | .pane_id')
[ ${#panes[@]} -gt 0 ] || exit 0

# herdr refuses to move a pane out of a zoomed tab.
[ "$(herdr pane layout --pane "${panes[0]}" | jq -r '.result.layout.zoomed')" != true ] \
  || herdr pane zoom --pane "${panes[0]}" --off > /dev/null
moved="$(herdr pane move "${panes[0]}" --new-workspace ${label_args[@]+"${label_args[@]}"} --focus)"
new_tab="$(jq -r '.result.move_result.created_tab.tab_id' <<< "$moved")"
last="$(jq -r '.result.move_result.pane.pane_id' <<< "$moved")"
for pane in "${panes[@]:1}"; do
  moved="$(herdr pane move "$pane" --tab "$new_tab" --split right --target-pane "$last" --no-focus)"
  last="$(jq -r '.result.move_result.pane.pane_id' <<< "$moved")"
done
