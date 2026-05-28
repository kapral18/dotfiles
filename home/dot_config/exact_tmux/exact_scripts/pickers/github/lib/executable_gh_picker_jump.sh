#!/usr/bin/env bash
# Jump the GitHub picker cursor to the next or previous section header.
# Called by fzf `transform` bindings (alt-n / alt-p); outputs an fzf action.
#
# Args: <mode_file> <scope_file> <direction>  where direction = next | prev
#
# Hot path is pure bash with zero subprocess spawns. `transform` blocks fzf
# input while it runs and fires once per keypress, so the previous `cat` +
# `python3` spawns (~85ms/press) made held or rapid alt-n/alt-p queue up and
# drain serially — the cursor crawled section by section until the backlog
# cleared. `$(<file)` reads plus a bash regex loop keep each press to this
# script's own startup, so bursts stay real-time.
set -euo pipefail

mode_file="${1:-}"
scope_file="${2:-}"
direction="${3:-}"

if [ -z "$mode_file" ] || [ -z "$scope_file" ] || [ -z "$direction" ]; then
  exit 0
fi
if [ "$direction" != "next" ] && [ "$direction" != "prev" ]; then
  exit 0
fi

mode="work"
scope="all"
[ -f "$mode_file" ] && IFS= read -r mode < "$mode_file" 2> /dev/null || true
[ -f "$scope_file" ] && IFS= read -r scope < "$scope_file" 2> /dev/null || true
[ -n "$mode" ] || mode="work"
[ -n "$scope" ] || scope="all"

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/tmux"
offsets_file="${cache_dir}/gh_picker_offsets_${mode}_${scope}.json"
[ -f "$offsets_file" ] || exit 0

cursor="${FZF_POS:-1}"
case "$cursor" in
  '' | *[!0-9]*) cursor=1 ;;
esac

blob=$(< "$offsets_file") || exit 0

# Collect every "row": N integer in document order (ascending) without spawning
# a JSON parser. Header titles never contain the literal `"row":`, so the match
# is unambiguous.
rows=()
rest="$blob"
row_re='"row":[[:space:]]*([0-9]+)'
while [[ "$rest" =~ $row_re ]]; do
  rows+=("${BASH_REMATCH[1]}")
  rest="${rest#*"${BASH_REMATCH[0]}"}"
done

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
