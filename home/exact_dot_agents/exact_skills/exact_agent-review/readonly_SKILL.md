---
name: agent-review
description: Agentic review orchestration that reuses the review skill's methodology without mutating it. Use when the user invokes /agent-review, asks for multi-agent review orchestration, or wants reviewer subagents plus finding aggregation before any fixes/comments.
---

# Agent Review

Orchestrate the review skill through investigation-only subagents, then aggregate before any side effect. This skill is a new orchestration surface; the existing `review` skill and its reference files remain the source-of-truth methodology and must not be edited for this flow.

## Source material

Read these files as common review base:

- `~/.agents/skills/review/SKILL.md` for routing: PR review, PR fix, local changes.
- `~/.agents/skills/review/references/judging_core.md` for truth validation, state-machine/deletion/history gates, coverage, severity, and the four-dimension lens.
- `~/.agents/skills/review/references/shared_rules.md` for read-only probes, base context, SCSI, CI coverage, draft style, verdict, persistence, and posting boundaries.
- For PR modes, `~/.agents/skills/review/references/pr_common.md`.
- The selected mode file: `local_changes.md`, `pr_review.md`, or `pr_fix.md`.

## Dissect the review skill by side-effect boundary

Subagents may use only investigation-safe parts of the review methodology:

- read-only routing and scope discovery (`git status`, diffs, PR metadata, threads, references, CI/check metadata)
- base-context discovery (SCSI when available, `git show <base>:<path>`, local source reads)
- evidence gathering and falsification (`/tmp` repros, state-machine harnesses under `/tmp`, non-mutating test/probe commands)
- deletion-safety and historical-rationale investigation (`rg`, `git log`, `git blame`, read-only PR/issue views)
- candidate finding construction using the coverage checklist and severity definitions
- candidate comment/fix suggestions as proposals only
- four-dimension findings audit over candidate findings, or over a named fix diff when the controller explicitly supplies one
- manual live UI/runtime comparison evidence from `live-ui-review` when the user explicitly requested it

Subagents must not use action/side-effect parts of the review methodology:

- editing files, applying fixes, resolving hygiene findings, or re-gating after their own edits
- posting, submitting reviews, replying, resolving threads, labeling, committing, pushing, or changing GitHub state
- deciding what should be fixed, commented, resolved, approved, or requested

Only the controller running this skill may decide and perform side effects, and only after aggregating the investigation outputs and following the relevant `review`/`github`/`git` gates.

## Default orchestration

1. **Route and scope.** Use the `review` router read-only to choose local changes, PR review, or PR fix. Build a scope packet: mode, role, PR number or diff range, base branch, staged/unstaged state, thread IDs, user constraints, and expected output shape.
2. **Launch two investigation reviewers in parallel.**
   - GPT lane: `review-gpt-5-5-extra-high`.
   - Opus lane: `review-opus-4-8-xhigh-non-thinking`.
   Give each a distinct angle chosen from the actual change: correctness/regressions, tests/validation, simplicity/maintainability, types/API contracts, security, performance, deletion-safety, or state-machine behavior.
3. **Run findings audit on candidate findings.** After both reviewers finish, run `findings-auditor` over their candidate findings. It audits the finding set for redundancy, verbosity, semantic + logical duplication, and gaps. It is still investigation, not a decision.
4. **Aggregate.** Combine GPT reviewer output, Opus reviewer output, any manually supplied `live-ui-review` evidence, and the findings audit.
5. **Judge in the controller.** Apply the review skill's Deduplication + Truth Filter and severity model. Keep only implementation-verified, net-new findings. Drop duplicates, unsupported claims, CI-covered findings, and findings that only a worker asserted without evidence.
6. **Act only after judgment.**
   - Local/self-review modes: apply the selected fixes in the working tree, then run the repo's discovered quality gates and the normal post-review stage over the fix diff.
   - Reviewing someone else's PR: draft public-ready comments/suggestions only; do not edit code or post.
   - PR fix/thread modes: apply selected fixes or draft replies according to `pr_fix.md`; human-visible publishing stays gated.

## Manual live UI review probe

`live-ui-review` is not part of the default flow. Invoke it only when the user explicitly asks for live PR-vs-main UI/runtime comparison (for example, Playwriter/browser/Kibana instance checks). Before any Playwriter/browser probing, it must ask whether the PR/head and main/base instances are ready and proceed only after the user replies exactly `go`. Its output is evidence input for aggregation; it never edits, posts, resolves, commits, pushes, or decides.

## Output

Return:

- `Base context:` line from the review methodology.
- Investigation summary: what each reviewer and findings auditor found.
- Controller judgment: findings kept/dropped and why.
- Action taken or draft payloads, depending on mode.
- Remaining uncertainty or gated side effects.
- `Compatibility impact: none | removed (requested) | kept existing (requested)`.
