#!/usr/bin/env bash
# Jump the GitHub picker cursor to the next or previous section header.
# Called by fzf `transform` bindings (alt-n / alt-p); outputs an fzf action.
#
# Args: <next|prev> <matches_file>
set -euo pipefail

direction="${1:-}"
matches_file="${2:-}"
[ -f "$matches_file" ] || exit 0
case "$direction" in
  next | prev) ;;
  *) exit 0 ;;
esac
cursor="${FZF_POS:-1}"
case "$cursor" in
  '' | *[!0-9]*) exit 0 ;;
esac
rows=()
row=0
while IFS= read -r line; do
  row=$((row + 1))
  IFS=$'\037' read -r _display kind _repo number _rest <<< "${line//$'\t'/$'\037'}"
  if [ "$kind" = "header" ] && [[ "$number" =~ ^(pr|issue):[0-9]+$ ]]; then
    rows+=("$row")
  fi
done < "$matches_file"
((${#rows[@]})) || exit 0
target=""
if [ "$direction" = "next" ]; then
  for r in "${rows[@]}"; do
    if ((r > cursor)); then
      target="$r"
      break
    fi
  done
  [ -n "$target" ] || target="${rows[0]}"
else
  for ((i = ${#rows[@]} - 1; i >= 0; i--)); do
    r="${rows[i]}"
    if ((r < cursor)); then
      target="$r"
      break
    fi
  done
  [ -n "$target" ] || target="${rows[${#rows[@]} - 1]}"
fi
printf 'pos(%s)' "$target"
