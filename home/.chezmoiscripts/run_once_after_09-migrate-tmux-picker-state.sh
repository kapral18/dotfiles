#!/usr/bin/env bash
# Carry the session picker's frecency and the GitHub/palette preferences from
# the tmux-era cache dir to the herdr pickers' one, then drop the old dir.
set -euo pipefail

cache="${XDG_CACHE_HOME:-$HOME/.cache}"
old="$cache/tmux"
new="$cache/herdr-pickers"
[ -d "$old" ] || exit 0

mkdir -p "$new"
for f in pick_session_frecency.tsv palette_history.tsv gh_picker_sort gh_picker_scope gh_picker_collapsed; do
  if [ -e "$old/$f" ] && [ ! -e "$new/$f" ]; then
    cp -p "$old/$f" "$new/$f"
  fi
done
rm -rf -- "$old"
