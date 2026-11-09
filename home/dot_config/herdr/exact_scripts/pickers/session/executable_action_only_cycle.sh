#!/usr/bin/env bash
# alt-o filter: cycles all -> dirty -> review -> all.
#   action_only_cycle.sh <mode_file> <filter_cmd>  advance the mode; print reload + header actions
#   action_only_cycle.sh <mode_file> --header      print the header for the current mode
#
# The mode lives only in the pid-scoped mode file the picker exports as
# PICK_SESSION_ONLY_FILE; every reload reads it through lib/only_filter.py and
# every header restore reads it through --header, so neither can drop it.
set -euo pipefail

mode_file="${1:-}"
[ -n "$mode_file" ] || exit 0

header_for() {
  case "$1" in
    dirty) printf '%s' 'filter: dirty only   alt-o=next' ;;
    review) printf '%s' 'filter: review-needed only   alt-o=next' ;;
    *) printf '%s' '?=help  ctrl-/=preview  alt-y=copy  alt-o=filter  alt-c=new wt  alt-g=GitHub' ;;
  esac
}

cur=""
[ -f "$mode_file" ] && cur="$(cat "$mode_file" 2> /dev/null || true)"

if [ "${2:-}" = "--header" ]; then
  header_for "$cur"
  exit 0
fi

filter_cmd="${2:-}"
[ -n "$filter_cmd" ] || exit 0

case "$cur" in
  dirty) next="review" ;;
  review) next="" ;;
  *) next="dirty" ;;
esac
printf '%s' "$next" > "$mode_file" 2> /dev/null || true

command="$filter_cmd --force-order"
if [ -n "${PICK_SESSION_SORT_SOURCE_FILE:-}" ]; then
  command="{ $command | tee \"\${PICK_SESSION_SORT_SOURCE_FILE}.new.\$\$\"; mv -f \"\${PICK_SESSION_SORT_SOURCE_FILE}.new.\$\$\" \"\$PICK_SESSION_SORT_SOURCE_FILE\"; }"
fi

printf 'reload(%s)+change-header(%s)+first' "$command" "$(header_for "$next")"
