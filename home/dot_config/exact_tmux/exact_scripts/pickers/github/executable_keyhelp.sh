#!/usr/bin/env bash
set -euo pipefail

cat << 'EOF'
GitHub Picker Keybindings

Actions
  enter       checkout (batch if items marked)
  alt-A       hand off to ,ralph go (workspace + goal prompt)
  alt-b       checkout + Octo review (PRs)
  alt-o       open in browser
  alt-y       copy URL(s) to clipboard (marked items; falls back to current)

Multi-select
  tab         mark/unmark item
  shift-tab   unmark item
  alt-space   mark/unmark item

Comments
  alt-c       new comment (opens $EDITOR)
  alt-r       quote-reply a comment
  alt-d       edit your own comment

Preview
  alt-e       cycle: collapsed -> body -> all expanded
  ctrl-/      toggle preview
  ?           show this help in the preview panel

Navigation
  ctrl-s      switch work/home
  ctrl-r      refresh from GitHub
  alt-g       switch to sessions picker
  alt-j/k     page down/up
  shift-up/down    scroll preview (line)
  shift-left/right scroll preview (page)
EOF
