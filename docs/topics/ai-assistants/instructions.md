---
sidebar_position: 2
---

# Instructions

`home/readonly_AGENTS.md` is the one global instruction file. It loads into every session, so every line must earn its place. Hook messages and advisor prompts point to its sections instead of restating its rules; a hook message that tells the agent to act also names the limits on acting. Procedures that apply only in some turns live word for word in skills; the SOP keeps a short trigger and the safety limits each needs without the skill: `k-long-jobs`, `k-cleanup` (§3 step 7), and the Approval scope in `k-git/references/commit-push.md` (§5).

The operating rules require agents to run applicable checks and finish review without waiting for reminders. In Claude Code, Pi, OMP, and Codex, a risky change or a rule edit gets review rounds of two fresh reviewers each, with a fix loop, repeated without asking until a full round on the whole scope finds no new medium or higher issue; a cause that returns twice goes under `Open:` and stops driving the loop. In Claude Code (with `advisorModel` set) and OMP, a model also reviews the final answer; Claude Code's `stop-review` adds format and evidence-citation checks that need no model. Pi, Codex, and OpenCode have no model review of the final answer. In Claude Code a turn goes back at most once per stretch, with the review's concerns and the format checks' findings in one send-back ([Claude mods](tool-configs/claude.md#mods)). OMP's `Gate` sends all its concerns in its first review of a run, and later ones only for a break the agent's fix introduced or a concern held back for its 3-note cap. In every harness the intent-guard hooks also check each iteration against the task's intent card: the card rides with each prompt, an edit outside its scope gets a note, a zoom-out comes every 25 tool calls, and a stop goes back while a `Done when` item is open ([Staying on the goal](staying-on-goal.md)).

## Sections

The global file is authoritative; these links summarize its responsibilities:

1. [Intent and scope](../../../home/readonly_AGENTS.md#1-intent-and-scope) — require both scope and step authorization, finish authorized work, and stop only for user decisions. Publication, live-check, and ask-first gates still apply.
2. [Truth and evidence](../../../home/readonly_AGENTS.md#2-truth-and-evidence) — verify claims from current sources and distinguish evidence from assumptions.
3. [Work loop](../../../home/readonly_AGENTS.md#3-work-loop) — record intent and impact, implement, run scoped checks, review and fix findings, clean up, and report evidence. It defines verification limits and the review loop.
4. [Subagents](../../../home/readonly_AGENTS.md#4-subagents) — work inline by default; use broad read-only search agents and the prescribed review workflow.
5. [Side effects](../../../home/readonly_AGENTS.md#5-side-effects-and-publication) — resolve commit, push, publication, and secret-handling authority before acting.
6. [Tools](../../../home/readonly_AGENTS.md#6-tools-and-environment) — edit managed sources, use comma commands, and search narrowly.
7. [Memory and handoffs](../../../home/readonly_AGENTS.md#7-memory-and-handoffs) — keep reusable knowledge, task progress, and lasting preferences in their respective stores.
8. [Wording and responses](../../../home/readonly_AGENTS.md#8-response-shape) — resolve consequential ambiguity in all authored text; apply the response format to in-session replies.

Review fix authority follows `k-review/references/authorship.md` in every mode.
Fix scope includes omitted requirements and necessary consumers of the authorized request, not only files already present in its diff.

The [wording rule in §8](../../../home/readonly_AGENTS.md#8-response-shape) applies to all authored and edited text, including prose, docs, responses, and AI-facing instructions. Its response format remains specific to in-session replies. `k-anti-slop` routes artifact writing to the rule; `k-writing-great-skills` routes behavioral wording through `k-instruction-boundaries`. The shared reviewer prompt applies the rule to changed text generally.

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
Retain distinct requirements. Remove a rule only after verifying that no reachable invocation loses required behavior; assumed model defaults are not evidence.
