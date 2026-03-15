#!/usr/bin/env bash
set -euo pipefail

cat << 'EOF'
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
  ctrl-s          send command to selected session(s)
                    enters send mode: type command, enter=send, esc=cancel

GitHub
  alt-p           open PR in browser (if branch has a PR)
  alt-i           open issue in browser (if branch references an issue)

Preview
  ctrl-/          toggle preview panel (pane capture / git info)
  ?               show this help in the preview panel
  shift-up/down   scroll preview (line)
  shift-left/right scroll preview (page)

Notes
  - actions operate on the selected rows (multi-select aware)
  - killing/removing writes short-lived tombstones to avoid reappearing items
EOF
