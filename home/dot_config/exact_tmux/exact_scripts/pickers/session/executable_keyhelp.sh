#!/usr/bin/env bash
set -euo pipefail

cat << 'EOF'
pick_session keybindings

Navigation
  up/down arrows  move selection
  alt-j / alt-k   page down / page up
  alt-h / alt-l   first item / last item

Filter / Refresh
  type            filter (sort auto-toggles when query contains '/')
  alt-s           toggle fzf sort manually
  ctrl-r          refresh sessions sync; exact dirty icons update in background
                    query is preserved; cursor stays at the same row index
                    (use ctrl-u to clear the query manually)
  alt-r           force full refresh (blocks until complete, then reloads)
                    same query/cursor preservation as ctrl-r

Selection / Actions
  enter           open (switch/create)
  tab             toggle multi-select on current row
  ctrl-x          kill selected session(s) (optimistic hide)
  alt-x           remove selected worktree(s) (optimistic hide)
  alt-y           copy underlying path(s) to clipboard
  ctrl-s          send command to selected entries (any kind)
                    enters send mode: type command, enter=send, esc=cancel
                    sessions: command goes to a shell pane in each session
                    worktree/dir without a session: spawns the canonical
                    session first (same name as enter would), then sends
                    list auto-refreshes after spawning (no ctrl-r needed);
                    cursor stays at the same row index across the reload

GitHub
  alt-p           open PR in browser (if branch has a PR)
  alt-i           open issue in browser (if branch references an issue)
  alt-g           switch to GitHub picker (PRs/issues from gh-dash sections)

Preview
  ctrl-/          toggle preview panel (pane capture / git info)
  ?               show this help in the preview panel
  shift-up/down   scroll preview (line)
  shift-left/right scroll preview (page)

Notes
  - actions operate on the selected rows (multi-select aware)
  - killing/removing writes short-lived tombstones to avoid reappearing items
EOF
