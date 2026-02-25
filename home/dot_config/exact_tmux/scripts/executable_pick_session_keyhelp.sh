#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
pick_session keybindings

Navigation
  up/down arrows  move selection
  alt-j / alt-k   page down / page up
  alt-h / alt-l   first item / last item

Filter / Refresh
  type            filter
  ctrl-r          reload from cache+live overlay (immediate)
  alt-r           force background refresh (updates open picker)

Selection / Actions
  enter           open (switch/create)
  tab             toggle multi-select on current row
  ctrl-x          kill selected session(s) (optimistic hide)
  alt-x           remove selected worktree(s) (optimistic hide)

Help
  ctrl-/          toggle this help panel
  shift-up/down   scroll help (line)
  shift-left/right scroll help (page)

Notes
  - actions operate on the selected rows (multi-select aware)
  - killing/removing writes short-lived tombstones to avoid reappearing items
EOF
