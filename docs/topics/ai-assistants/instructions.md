---
sidebar_position: 2
---

# Instructions

`home/readonly_AGENTS.md` is the one global instruction file (about 6 KB). It loads into every session, so every line must earn its place.

## Sections

1. Intent and scope — act on requests, change only what is asked, no compatibility shims unless requested.
2. Truth and evidence — verify before claiming; local source first; treat model reports as leads.
3. Doing the work — read callers first; run checks once on the finished change; stop after two failed attempts without new evidence.
4. Subagents — inline by default; search and on-request review only; never loop review → fix → review.
5. Side effects — commit, push, or publish only when asked; human-visible text needs approval; CODEOWNERS check; secrets by reference.
6. Tools — chezmoi source-path rule, comma commands, zsh `NOMATCH`, narrow search.
7. Memory and handoffs — `,ai-kb` on demand; `,handoff` for task progress.
8. Response shape — ASD-STE100-style writing (sentence limits, active voice, stable terms), line 1 answers, word budgets, tables over prose.

## Where each harness reads it

| Harness     | Entry point                                                                              |
| ----------- | ---------------------------------------------------------------------------------------- |
| Claude Code | `~/.claude/CLAUDE.md` (symlink to `~/AGENTS.md`) and `~/CLAUDE.md` (`@AGENTS.md` import) |
| Pi          | `~/.pi/agent/AGENTS.md` symlink                                                          |
| OMP         | `~/.omp/agent/AGENTS.md` symlink, plus `APPEND_SYSTEM.md` for the subagent overlay       |
| Codex       | `~/.codex/AGENTS.md` symlink                                                             |
| OpenCode    | `~/.config/opencode/AGENTS.md` symlink                                                   |
| Antigravity | `~/.gemini/config/AGENTS.md` symlink                                                     |

The repo's own `AGENTS.md` adds dotfiles rules: chezmoi source of truth, `make fmt` / `make check`, docs updates, and skill naming.
Package, comma-command, and shell-helper changes follow [Dotfiles agent recipes](../workflow/dotfiles-recipes.md).

## Editing

Edit `home/readonly_AGENTS.md`, then `chezmoi apply --no-tty ~/AGENTS.md`. There is no compiler or generated copy.
Keep rules that change behavior; delete rules that restate model defaults.
