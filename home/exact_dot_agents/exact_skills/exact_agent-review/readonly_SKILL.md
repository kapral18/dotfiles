---
name: agent-review
description: Agentic review orchestration that reuses the review skill's methodology without mutating it. Use when the user invokes /agent-review, asks for multi-agent review orchestration, or wants reviewer subagents plus finding aggregation before any fixes/comments.
---

# Agent Review

This is the controller contract for `/agent-review`. The controller routes, delegates, aggregates, judges, and performs gated side effects; the substantive review work happens in isolated reviewer workers that load the shared `review` skill themselves.

Do not mutate the existing `review` skill or its references for this flow. They remain the source-of-truth methodology for worker investigation and post-aggregation gates.

## Controller boundary

The controller owns:

- route and scope discovery: local changes, PR review, or PR fix; PR number or diff range; base branch; staged/unstaged state; thread IDs; user constraints; expected output shape
- launching the two reviewer workers and the findings auditor
- aggregating worker outputs, optional `live-ui-review` evidence, and audit output
- judging kept/dropped findings after aggregation
- applying fixes, drafting payloads, or touching GitHub only after the relevant `review`/`github`/`git` gates

The controller must not load or run the full `review` skill before fan-out. It uses the user request and read-only target metadata to build the scope packet. After workers return, it may consult only the minimum relevant review references for deduplication, severity, and side-effect gates; it must not rerun the coverage checklist, base-context investigation, or worker review analysis.

Reviewer workers own the full investigation methodology. Their shared runtime contract is `~/.agents/skills/agent-review/references/runtime-contracts.md`. They load the `review` skill, `judging_core.md`, `shared_rules.md`, and the selected mode file inside their own contexts; for PR modes they also load `pr_common.md`. Workers and auditors return evidence and candidate findings only; they never edit, post, resolve, commit, push, or decide what should be fixed/commented on.

For runtime-specific worker names and fallbacks, read `~/.agents/skills/agent-review/references/runtime-harnesses.md`. Use the best supported native mechanism for the current harness; never invent a custom-agent layer the harness does not expose.

## Default orchestration

1. **Route and scope.** Build a scope packet: mode (`local_changes.md`, `pr_review.md`, or `pr_fix.md`), role, PR number or diff range, base branch, staged/unstaged state, thread IDs, user constraints, and expected output shape. Do not duplicate worker review analysis in the controller.
2. **Launch two investigation reviewers in parallel.** Use the runtime's supported worker lanes from `runtime-harnesses.md`. Give each the scope packet and a distinct angle chosen from the actual change: correctness/regressions, tests/validation, simplicity/maintainability, types/API contracts, security, performance, deletion-safety, or state-machine behavior. The workers load and apply the review methodology.
3. **Run findings audit on candidate findings.** After both reviewers finish, run `findings-auditor` over their candidate findings. It audits the finding set for redundancy, verbosity, semantic + logical duplication, and gaps. It is still investigation, not a decision.
4. **Aggregate.** Combine GPT reviewer output, Opus reviewer output, any manually supplied `live-ui-review` evidence, and the findings audit.
5. **Judge in the controller.** Apply the review skill's Deduplication + Truth Filter and severity model to the aggregated evidence. Keep only implementation-verified, net-new findings. Drop duplicates, unsupported claims, CI-covered findings, and findings that only a worker asserted without evidence.
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
