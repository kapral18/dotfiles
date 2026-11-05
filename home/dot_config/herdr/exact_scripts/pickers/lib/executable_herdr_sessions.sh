#!/usr/bin/env bash
# Session rows for the picker's Python helpers.
#   list     "<label>\t<path>" per workspace (exit 1 when herdr cannot be queried)
#   names    one label per line
#   current  label of the workspace the picker was opened from
set -euo pipefail
# shellcheck source=herdr_ws.sh
. "$HOME/.config/herdr/scripts/pickers/lib/herdr_ws.sh"

case "${1:-}" in
  list)
    herdr workspace list > /dev/null || exit 1
    hws_list
    ;;
  names)
    herdr workspace list > /dev/null || exit 1
    hws_list | cut -f1
    ;;
  current) hws_current ;;
  *) exit 2 ;;
esac
