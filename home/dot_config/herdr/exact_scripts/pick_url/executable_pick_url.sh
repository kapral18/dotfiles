#!/usr/bin/env bash
# herdr popup: list URLs visible in the pane under the popup and open the picks.
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"

die() {
  printf '\n  %s\n' "$1"
  read -rsn1 -t 3 _ || true
  exit 0
}

for cmd in fzf herdr; do
  command -v "$cmd" > /dev/null 2>&1 || die "missing command: $cmd"
done
pane="${HERDR_ACTIVE_PANE_ID:-}"
[ -n "$pane" ] || die "no active pane"

extra_filter="${PICK_URL_EXTRA_FILTER:-}"
limit="${PICK_URL_HISTORY_LIMIT:-screen}"
read_args=(--source visible)
if [[ "$limit" =~ ^[0-9]+$ ]]; then
  read_args=(--source recent-unwrapped --lines "$limit")
else
  limit="$(herdr pane get "$pane" 2> /dev/null \
    | jq -r '.result.pane.scroll | (.viewport_rows + .offset_from_bottom)' 2> /dev/null || true)"
  # herdr caps --lines at 1000; past that (or without a size), read the screen as shown.
  if [[ "$limit" =~ ^[0-9]+$ ]] && [ "$limit" -le 1000 ]; then
    read_args=(--source recent-unwrapped --lines "$limit")
  fi
fi

items="$(herdr pane read "$pane" "${read_args[@]}" --ansi \
  | python3 "$script_dir/lib/strip_cr.py" --extract-candidates --extra-filter "$extra_filter" \
  | nl -w3 -s '  ')" || die "could not read the pane"
[ -n "$items" ] || die "no URLs found"

selected="$(FZF_DEFAULT_OPTS='' fzf --multi --exit-0 --no-preview <<< "$items" || true)"
[ -n "$selected" ] || exit 0

sed -E 's/^[[:space:]]*[0-9]+[[:space:]]+//' <<< "$selected" | while IFS= read -r url; do
  [ -n "$url" ] || continue
  if [ -n "${PICK_URL_OPEN_CMD:-}" ]; then
    "$PICK_URL_OPEN_CMD" "$url"
  else
    open "$url"
  fi
done > /dev/null 2>&1
