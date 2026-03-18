#!/usr/bin/env bash
set -euo pipefail

meta="${1:-}"
out_file="${2:-}"

[ -n "$out_file" ] || exit 0

kind=""
num=""
url=""
extract_url() {
  local s="${1:-}"
  case "$s" in
    *https://*)
      printf 'https://%s' "${s#*https://}"
      return 0
      ;;
    *http://*)
      printf 'http://%s' "${s#*http://}"
      return 0
      ;;
  esac
  return 1
}
case "$meta" in
  *'|issue='*)
    kind="issue"
    tmp="${meta##*|issue=}"
    num="${tmp%%:*}"
    url="$(extract_url "$tmp" 2> /dev/null || true)"
    ;;
  *'|pr='*)
    kind="pr"
    tmp="${meta##*|pr=}"
    num="${tmp%%:*}"
    url="$(extract_url "$tmp" 2> /dev/null || true)"
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
