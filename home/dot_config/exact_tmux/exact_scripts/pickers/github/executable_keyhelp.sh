#!/usr/bin/env bash
set -euo pipefail

cat << 'EOF'
GitHub Picker Keybindings

Actions
  enter       checkout (batch if items marked)
  alt-i       create issue (opens $EDITOR; optional worktree + session)
  alt-E       create epic (parent + authored sub-issues; optional worktree)
  alt-x       command palette (close, reopen, approve, merge, label, comment, rr)
  alt-A       hand off selection to ,ralph go (workspace + context + goal prompt)
  alt-b       checkout + Octo review (PRs)
  alt-o       open in browser
  alt-y       copy URL(s) to clipboard (marked items; falls back to current)

Multi-select
  tab         mark/unmark item
  shift-tab   unmark item
  alt-space   mark/unmark item
  alt-M       mark entire family (parent + all its children)

Hierarchy
  alt-z       collapse/expand the family under the cursor (▸ / ▾)
  alt-Z       global collapse-all / expand-all toggle
  ↳ #N        cross-link badge: closing PR (issue rows) / closed issue (PR rows)
  filter      type `closes:N`, `closed-by:N`, or `linked` in the fzf prompt to
              filter cross-linked rows; e.g. `linked` shows every cross-linked
              item, `closes:239902` finds the PR that closes issue #239902

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
  alt-0       show all sections
  alt-1       focus scope (Action: + Mine: + Maintenance: sections — work you own / must act on)
  alt-2       explore scope (Watching: sections — informational)
  alt-n/p     jump to next/previous section header (wraps)
  alt-S       cycle sort: created-desc -> updated-desc -> age-asc -> repo-asc
  alt-j/k     page down/up
  shift-up/down    scroll preview (line)
  shift-left/right scroll preview (page)
EOF
