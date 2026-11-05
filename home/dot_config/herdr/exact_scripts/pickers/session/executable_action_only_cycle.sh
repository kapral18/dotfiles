#!/usr/bin/env bash
# alt-o transform helper: cycles the picker's "only" filter across
#   all -> dirty -> review -> all
# and prints an fzf action string (reload + change-header) for the new mode.
#
# State is held in a pid-scoped flag file so each picker instance cycles
# independently. The reload routes through filter.sh --only=<mode>, which
# filters rows by the cache `meta` column before grouping.
set -euo pipefail

mode_flag="${1:-}"
filter_cmd="${2:-}"
[ -n "$mode_flag" ] || exit 0
[ -n "$filter_cmd" ] || exit 0

cur=""
[ -f "$mode_flag" ] && cur="$(cat "$mode_flag" 2> /dev/null || true)"

case "$cur" in
  dirty) next="review" ;;
  review) next="" ;;
  *) next="dirty" ;;
esac

printf '%s' "$next" > "$mode_flag" 2> /dev/null || true

case "$next" in
  dirty)
    header='filter: dirty only   alt-o=next'
    command="$filter_cmd --force-order --only=dirty"
    ;;
  review)
    header='filter: review-needed only   alt-o=next'
    command="$filter_cmd --force-order --only=review"
    ;;
  *)
    header='?=help  ctrl-/=preview  alt-y=copy  alt-o=filter  alt-c=new wt  alt-g=GitHub'
    command="$filter_cmd --force-order"
    ;;
esac

if [ -n "${PICK_SESSION_SORT_SOURCE_FILE:-}" ]; then
  command="{ $command | tee \"\${PICK_SESSION_SORT_SOURCE_FILE}.new.\$\$\"; mv -f \"\${PICK_SESSION_SORT_SOURCE_FILE}.new.\$\$\" \"\$PICK_SESSION_SORT_SOURCE_FILE\"; }"
fi
reload="reload($command)"

printf '%s+change-header(%s)+first' "$reload" "$header"
