---
sidebar_position: 2
---

# Instructions

`home/readonly_AGENTS.md` is the one global instruction file (about 10 KB). It loads into every session, so every line must earn its place.

## Sections

1. Intent and scope — act on requests, change only what is asked, no compatibility shims unless requested; apply fixes checked against source, inside write scope and `k-review` Fix Scope, without asking, and list them under `Assumptions:`; a decision that is the user's goes last, under `Decision needed:`.
2. Truth and evidence — verify before claiming; local source first; treat model reports as leads.
3. Work loop — read callers and separate task edits from existing work; check and run the finished change; review risky changes once; fix supported findings; report evidence and open issues. `k-review/references/review_fixes.md` owns the bounded fix procedure. The SOP keeps its triggers and caps.
4. Subagents — inline by default; search subagent for broad read-only searches; a review the user asks for goes through `k-review`; the §3 reviews are the only delegated verification.
5. Side effects — commit, push, or publish only when asked; human-visible text needs approval; CODEOWNERS check; secrets by reference.
6. Tools — edit chezmoi sources for managed targets, writable files directly otherwise; comma commands, zsh `NOMATCH`, narrow search.
7. Memory and handoffs — `,ai-kb` on demand; `,behavior-map` checked before and updated after code changes, with unmapped areas mapped first; `,handoff` for task progress.
8. Response shape — ASD-STE100-style writing (sentence limits, active voice, stable terms), line 1 answers, word budgets, tables over prose.

Review fix authority follows `k-review/references/authorship.md` in every mode.
Fix scope includes omitted requirements and necessary consumers of the authorized request, not only files already present in its diff.

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
