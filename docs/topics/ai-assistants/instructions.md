---
sidebar_position: 2
---

# Instructions

`home/readonly_AGENTS.md` is the one global instruction file. It loads into every session, so every line must earn its place. Hook messages and advisor prompts point to its sections instead of restating its rules; a hook message that tells the agent to act also names the limits on acting. Procedures that apply only in some turns live word for word in skills; the SOP keeps a short trigger and the safety limits each needs without the skill: `k-long-jobs`, `k-cleanup` (§3 step 7), and the Approval scope in `k-git/references/commit-push.md` (§5).

Checks run automatically, so the user never has to nudge the agent to review again or finish the work. In Claude Code, Pi, OMP, and Codex, a risky change or a rule edit gets review rounds of two fresh reviewers each, with a fix loop, repeated without asking until a full round on the whole scope finds no new medium or higher issue; a cause that returns twice goes under `Open:` and stops driving the loop. In Claude Code (with `advisorModel` set) and OMP, a model also reviews the final answer; Claude Code's `stop-review` adds format and evidence-citation checks that need no model. Pi, Codex, and OpenCode have no model review of the final answer. In Claude Code a turn goes back at most once per stretch, with the review's concerns and the format checks' findings in one send-back ([Claude mods](tool-configs/claude.md#mods)). OMP's `Gate` sends all its concerns in its first review of a run, and later ones only for a break the agent's fix introduced or a concern held back for its 3-note cap. In every harness the intent-guard hooks also check each iteration against the task's intent card: the card rides with each prompt, an edit outside its scope gets a note, a zoom-out comes every 25 tool calls, and a stop goes back while a `Done when` item is open ([Staying on the goal](staying-on-goal.md)).

## Sections

1. Intent and scope — act on requests, change only what is asked plus defects in the change's impact, no compatibility shims unless requested; finish the task without stopping for a yes the user would give: do every named or reversible local step in scope (fixes from a review the request ran on the user's own work count) or that fixes an impact defect, plus the cleanup `k-cleanup` allows, never a §5 action §5 does not allow, an unrequested live check, or a step the user asked to be asked about first; stop only for what needs the user's judgment (a goal or preference evidence cannot settle, overriding their explicit choice, an in-scope step or impact-defect fix the do-list leaves out, a dilemma, or a question they asked for), last, under `Decision needed:` with a pick; at any other fork take the option the user would agree with and list it under `Assumptions:`; anything else goes in its §3 step 8 list.
2. Truth and evidence — verify before claiming, and say Unknown only after trying the tools; local source first; treat model reports as leads; evidence from before a later change does not count.
3. Work loop — write the intent card (`,task card set`) before the first edit and mark its items as they are met; read callers, collect the impact list both ways (what it can break; for new or changed behavior, every domain and scope it must fit) and from it the change's impact (what depends on, copies, or must fit the change, plus a defect with one reasonable reversible fix in a file it touches; §3 step 1 sets the exclusions), and separate task edits from existing work; check the finished change with unit and static checks scoped to it and verify it statically, so feedback reaches the user and any orchestrating agent quickly (read the source of systems it relies on, run local code that ends on its own, every check under a time limit set above its normal run time, none repeated without new information; a live check, as step 4 defines it, runs only on the user's ask), with operations against each other and edge inputs; review risky changes and rule edits with two fresh reviewers per round; fix every supported finding the change caused, the request covers, or the change's impact holds, the whole class rather than one instance, stepping back to the user's goal before each fix round, with fix-diff reviews while a medium or higher issue remains, and run another full round without asking while one finds a new medium or higher issue, narrowing later rounds to what fixes touched, until a full round on the whole change is clean (a cause that returns twice goes under `Open:` and stops driving the loop); clean up what the task left; do every doable step in the request's scope or the change's impact before reporting; report evidence and open issues, with no other list for undone work. `k-review/references/review_fixes.md` owns the fix procedure.
4. Subagents — inline by default; search subagent for broad read-only searches; reviews go through `k-review`.
5. Side effects — commit only after a commit or push request, push only after a push request (a PR request is both), and that request carries over to `continue <topic>` when the handoff note lists it under `Approvals:` (any other new session starts a new task); history-rewriting pushes, PR merges, and publishing need their own request; human-visible text needs approval, except the title and body of a PR the user asked for and replies on a PR the agent opened in the task; secrets by reference.
6. Tools — edit chezmoi sources for managed targets, writable files directly otherwise; comma commands, zsh `NOMATCH`, narrow search.
7. Memory and handoffs — `,ai-kb` on demand; `,task pref add` for a lasting preference the user states; `,handoff` for task progress, including commit or push approvals that carry over. `,behavior-map` is checked before and updated after code changes, with unmapped areas mapped first.
8. Response shape — line 1 answers, word budgets, tables over prose; after a hook or advisor sends the final answer back, the whole current answer again, never a delta. Platform and system instructions stay authoritative, except the verification defaults that §3 step 4 replaces; §8 sets tone and format where they leave it open.

Review fix authority follows `k-review/references/authorship.md` in every mode.
Fix scope includes omitted requirements and necessary consumers of the authorized request, not only files already present in its diff.

## Disagreement and correction

[SOP §2](../../../home/readonly_AGENTS.md#2-truth-and-evidence) forbids pandering: criticism prompts a check, not an automatic concession or promise to edit. The agent explains supported reasoning, names uncertainty, and corrects confirmed mistakes. Changed goals or preferences can change a recommendation without making the earlier factual claim false.

Deslop applies this rule before removing a criticized pattern. External replies distinguish confirmed, refuted, and unsettled findings before choosing acknowledgment or disagreement. The shared reviewer prompt requires evidence for either verdict and has no finding quota. The [evidence ledger](staying-on-goal.md#evidence-and-decisions) checks source provenance and stance freshness in code and keeps resolved findings for later reviews. It cannot prove that evidence supports a claim or guarantee future model adherence.

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
