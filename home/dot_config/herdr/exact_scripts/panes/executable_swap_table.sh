#!/usr/bin/env bash
# herdr popup for prefix+s, the tmux "k18" key table: the next key swaps the
# active pane with its neighbor (h/j/k/l) or moves the active tab (H/L).
set -euo pipefail

pane="${HERDR_ACTIVE_PANE_ID:-}"
tab="${HERDR_ACTIVE_TAB_ID:-}"
ws="${HERDR_ACTIVE_WORKSPACE_ID:-}"
[ -n "$pane" ] && [ -n "$tab" ] && [ -n "$ws" ] || exit 0

printf ' swap pane h/j/k/l · move tab H/L'
IFS= read -rsn1 key || exit 0

notify() {
  herdr notification show "swap" --body "$1" > /dev/null 2>&1 || true
}

# Same wrap-around as herdr's move_tab_previous/next: past either end the tab
# goes to the other end. insert_index counts gaps, so moving right skips one.
move_tab() {
  local step="$1" idx count insert reply
  read -r idx count < <(herdr tab list --workspace "$ws" | jq -r --arg tab "$tab" \
    '.result.tabs | [((map(.tab_id) | index($tab)) // -1), length] | @tsv') || {
    notify "tab list failed"
    return 0
  }
  [ "$idx" -ge 0 ] && [ "$count" -gt 1 ] || return 0
  if [ "$step" -lt 0 ]; then
    if [ "$idx" -eq 0 ]; then insert="$count"; else insert=$((idx - 1)); fi
  else
    if [ "$idx" -eq $((count - 1)) ]; then insert=0; else insert=$((idx + 2)); fi
  fi
  reply="$(python3 -c '
import json, socket, sys
s = socket.socket(socket.AF_UNIX)
s.connect(sys.argv[1])
s.sendall((json.dumps({"id": "swap_table", "method": "tab.move", "params": {"tab_id": sys.argv[2], "insert_index": int(sys.argv[3])}}) + "\n").encode())
print(s.makefile().readline())
' "$HERDR_SOCKET_PATH" "$tab" "$insert" 2>&1)" || reply='{"error":"socket"}'
  jq -e 'has("error") | not' <<< "$reply" > /dev/null 2>&1 || notify "tab move failed: $reply"
}

swap() {
  herdr pane swap --pane "$pane" --direction "$1" > /dev/null 2>&1 || notify "pane swap $1 failed"
}

case "$key" in
  h) swap left ;;
  j) swap down ;;
  k) swap up ;;
  l) swap right ;;
  H) move_tab -1 ;;
  L) move_tab 1 ;;
  *) ;;
esac
