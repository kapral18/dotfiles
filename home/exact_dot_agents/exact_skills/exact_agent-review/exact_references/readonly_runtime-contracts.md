# Agent Review Runtime Contracts

Shared contracts for `/agent-review` runtime subagents. Runtime profiles should stay thin: they select the lane/model and load the relevant section from this file.

## Reviewer worker

Use for `review-gpt-5-5-extra-high`, `review-opus-4-8-xhigh-non-thinking`, and equivalent read-only review lanes.

The parent controller supplies a scope packet: mode (`local_changes.md`, `pr_review.md`, or `pr_fix.md`), role, PR number or diff range, base branch, staged/unstaged state, thread IDs, user constraints, expected output shape, and assigned review angle.

Load `~/.agents/skills/review/SKILL.md`, `references/judging_core.md`, `references/shared_rules.md`, and the mode file named by the parent. For PR modes, also load `pr_common.md`. Do not launch more subagents.

Hard constraints:

- Strictly read-only: never edit files, never run state-changing commands, never post or submit to GitHub.
- Establish base context exactly as the review skill requires.
- Verify every finding from evidence; drop guesses and duplicates.
- Where a mode would normally fix or post, report the precise fix or draft comment for the parent controller to act on.

Return only findings for the assigned angle, ordered by severity. Include: `Base context: ...`, where, what is wrong, why it matters, how to verify, and the smallest proposed fix. Do not return raw diffs or logs.

## Findings auditor

Use after the two reviewer workers finish, before controller action. The subject is not the original review target and not a working-tree fix; the subject is the candidate finding set produced by the reviewer workers.

Load `~/.agents/skills/review/references/judging_core.md` and apply only the **Post-Review Lens (The Four Dimensions)**. Do not run the full coverage checklist, base-context gate, semantic search gate, or GitHub machinery.

Scope:

- Audit the combined candidate findings from `review-gpt-5-5-extra-high` and `review-opus-4-8-xhigh-non-thinking`.
- If the parent explicitly names a commit range, staged set, uncommitted diff, or files, audit that fix diff instead.

Hard constraints:

- Strictly read-only: never edit files, never run state-changing commands, never post to GitHub, and never decide what should be fixed or commented on.
- Verify every hygiene finding from evidence; do not assert a problem without an exact anchor.
- Group findings by the canonical dimensions: redundancy, verbosity, semantic + logical duplication, gaps.

Return each finding with: where, what is wrong, why it matters, and the smallest proposed cleanup. If a dimension is clean, say so for that dimension. Do not return raw diffs or logs.

## Live UI review

Use only when the user explicitly asks for live UI/runtime comparison, such as checking a PR deployment against a main/base deployment before review aggregation. This agent is not part of the default `/agent-review` flow.

### Readiness checkpoint

Before any Playwriter/browser probing, ask the user whether the PR/head and main/base instances are ready for live UI testing. Include any URLs or missing setup details needed in that checkpoint. Proceed only after the user replies exactly `go`.

If the user does not reply `go`, stop and report what is needed. Do not open a browser, run Playwriter, or perform live UI probes.

After `go`, if using Playwriter, follow `~/.agents/skills/playwriter/SKILL.md` and run `playwriter skill` before the first Playwriter command.

Scope:

- Compare the named PR/head runtime against the named main/base runtime.
- Use non-mutating probes only: browser inspection, HTTP requests, screenshots/paths when available, logs, or read-only CLI commands.
- Capture concrete evidence: URLs, steps, screenshots/paths when available, observed differences, and uncertainty.

Hard constraints:

- Investigation only. Never edit files, post comments, resolve threads, commit, push, or decide what the controller should fix/comment on.
- Return findings to the user or `/agent-review` as evidence input. `/agent-review` performs any judgment or side effects.
