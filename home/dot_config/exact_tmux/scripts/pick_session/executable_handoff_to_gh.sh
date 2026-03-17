#!/usr/bin/env bash
set -euo pipefail

meta="${1:-}"
out_file="${2:-}"

[ -n "$out_file" ] || exit 0

kind=""
num=""
url=""
case "$meta" in
  *'|issue='*)
    kind="issue"
    tmp="${meta##*|issue=}"
    num="${tmp%%:*}"
    url="${tmp#*:}"
    url="${url#*:}"
    ;;
  *'|pr='*)
    kind="pr"
    tmp="${meta##*|pr=}"
    num="${tmp%%:*}"
    url="${tmp#*:}"
    url="${url#*:}"
    url="${url#*:}"
    url="${url#*:}"
    ;;
esac

repo=""
case "$url" in
  https://github.com/*/*)
    path="${url#https://github.com/}"
    owner="${path%%/*}"
    rest="${path#*/}"
    name="${rest%%/*}"
    if [ -n "$owner" ] && [ -n "$name" ] && [ "$owner" != "$path" ]; then
      repo="${owner}/${name}"
    fi
    ;;
esac

printf '%s\t%s\t%s\n' "$kind" "$repo" "$num" > "$out_file" 2> /dev/null || true
