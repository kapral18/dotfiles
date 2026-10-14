---
sidebar_position: 2
---

# Instructions

`home/readonly_AGENTS.md` is the one global instruction file (about 10 KB). It loads into every session, so every line must earn its place. Hook messages and advisor prompts point to its sections instead of restating its rules; a hook message that tells the agent to act also names the limits on acting. Procedures that apply only in some turns live word for word in skills; the SOP keeps a short trigger and the safety limits each needs without the skill: `k-long-jobs`, `k-cleanup` (§3 step 7), and the Approval scope in `k-git/references/commit-push.md` (§5).

Checks run automatically, so the user never has to nudge the agent to review again or finish the work. In Claude Code, Pi, OMP, and Codex, a risky change or a rule edit gets review rounds of two fresh reviewers each, with a fix loop, repeated until a round finds no new medium or higher issue, three rounds have run, or a cause returns twice. In Claude Code (with `advisorModel` set) and OMP, a model also reviews the final answer; Claude Code's `stop-review` adds format checks that need no model. Pi, Codex, and OpenCode have no final-answer hooks. In Claude Code a turn goes back at most once, with the review's concerns and the format checks' findings in that one send-back, on the answer that would end the turn (an answer another Stop hook such as `/goal` sends back is left to it), because each extra send-back made the agent rewrite its whole answer again; the rewritten answer is not checked again. OMP's `Gate` sends all its concerns in its first review of a run, and later ones only for a break the agent's fix introduced or a concern held back for its 3-note cap.

## Sections

1. Intent and scope — act on requests, change only what is asked, no compatibility shims unless requested; do any in-scope next step the request named, or any reversible one that changes nothing outside this machine the request did not name, without asking (unless the user asked you to ask first), and finish every item of an "all of X" request; never ask approval for a fix checked against source; ask only for a decision that is the user's (including a step the request did not name that is not reversible or changes something outside this machine the request did not name), last, under `Decision needed:`; otherwise pick a default and list it under `Assumptions:`.
2. Truth and evidence — verify before claiming, and say Unknown only after trying the tools; local source first; treat model reports as leads; evidence from before a later change does not count.
3. Work loop — read callers, know what must change with the code, and separate task edits from existing work; check the finished change and run it, with operations against each other and edge inputs; review risky changes and rule edits with two fresh reviewers per round; fix every supported finding the change caused or the request covers, stepping back to the user's goal before each fix round, with up to three fix-diff reviews per round, and run another full round while one finds a new medium or higher issue, up to three rounds or a cause that returns twice; clean up what the task left; do every doable in-scope step before reporting; report evidence and open issues, with no other list for undone work. `k-review/references/review_fixes.md` owns the bounded fix procedure.
4. Subagents — inline by default; search subagent for broad read-only searches; reviews go through `k-review`.
5. Side effects — commit only after a commit or push request, push only after a push request (a PR request is both), and that request carries over to `continue <topic>` when the handoff note lists it under `Approvals:` (any other new session starts a new task); history-rewriting pushes, PR merges, and publishing need their own request; human-visible text needs approval, except the title and body of a PR the user asked for and replies on a PR the agent opened in the task; secrets by reference.
6. Tools — edit chezmoi sources for managed targets, writable files directly otherwise; comma commands, zsh `NOMATCH`, narrow search.
7. Memory and handoffs — `,ai-kb` on demand; `,handoff` for task progress, including commit or push approvals that carry over. `,behavior-map` is checked before and updated after code changes, with unmapped areas mapped first.
8. Response shape — line 1 answers, word budgets, tables over prose; after a hook or advisor sends the final answer back, the whole current answer again, never a delta. Platform and system instructions stay authoritative; §8 sets tone and format where they leave it open.

Review fix authority follows `k-review/references/authorship.md` in every mode.
Fix scope includes omitted requirements and necessary consumers of the authorized request, not only files already present in its diff.

## Where each harness reads it

| Harness     | Entry point                                                                           |
| ----------- | ------------------------------------------------------------------------------------- |
| Claude Code | `~/.claude/CLAUDE.md` and `~/CLAUDE.md`, both symlinks to `~/AGENTS.md` (loaded once) |
| Pi          | `~/.pi/agent/AGENTS.md` symlink                                                       |
| OMP         | `~/.omp/agent/AGENTS.md` symlink, plus `APPEND_SYSTEM.md` for the workflow overlay    |
| Codex       | `~/.codex/AGENTS.md` symlink                                                          |
| OpenCode    | `~/.config/opencode/AGENTS.md` symlink                                                |

The repo's own `AGENTS.md` adds dotfiles rules: chezmoi source of truth, `make fmt` / `make check`, docs updates, and skill naming.
Package, comma-command, and shell-helper changes follow [Dotfiles agent recipes](../workflow/dotfiles-recipes.md).

## Editing

Edit `home/readonly_AGENTS.md`, then `chezmoi apply --no-tty ~/AGENTS.md`. There is no compiler or generated copy.
Keep rules that change behavior; delete rules that restate model defaults.
