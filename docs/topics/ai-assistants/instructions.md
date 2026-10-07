---
sidebar_position: 2
---

# Instructions

`home/readonly_AGENTS.md` is the one global instruction file (about 9 KB). It loads into every session, so every line must earn its place.

## Sections

1. Intent and scope — act on requests, change only what is asked, no compatibility shims unless requested; apply fixes checked against source, inside write scope and `k-review` Fix Scope, without asking.
2. Truth and evidence — verify before claiming; local source first; treat model reports as leads.
3. Work loop — rules for every step (check evidence before a destructive command; stop after two failed attempts without new evidence; scratch in `/tmp`), then seven ordered steps per change: Before (read callers; `k-behavior-map` check), Change (several hypotheses), Check (project checks once on the finished change; after a fix, rerun only failed and affected checks), Run (once on a realistic target; operations against each other and against edge inputs; the real command on those inputs, on a copy, where a test fake replaces it; then `k-behavior-map` update), Review (for a risky change: new command or module; persisted state, a parser, or concurrency; a rule or workflow step in the SOP, a skill, or a `k-agent-*` profile — two parallel reviewers on the whole task change with its map and memory writes), Fix (fix every supported finding; one reviewer checks each fix diff until no supported medium or higher finding remains, at most three times, or until the same cause comes back at the same place), and Report (`Checked:`, `Known gaps:`, `Open:`; done means no known issue of medium or higher). A skipped step is named with its reason.
4. Subagents — inline by default; search subagent for broad read-only searches; a review the user asks for goes through `k-review`; the §3 reviews are the only delegated verification.
5. Side effects — commit, push, or publish only when asked; human-visible text needs approval; CODEOWNERS check; secrets by reference.
6. Tools — chezmoi source-path rule, comma commands, zsh `NOMATCH`, narrow search.
7. Memory and handoffs — `,ai-kb` on demand; `,behavior-map` checked before and updated after code changes, with unmapped areas mapped first; `,handoff` for task progress.
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
