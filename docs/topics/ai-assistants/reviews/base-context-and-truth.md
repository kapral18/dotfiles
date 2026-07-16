---
sidebar_position: 2
title: Base context and truth validation
---

# Base context and truth validation

Review decisions compare the diff under review with the codebase reality it is changing. This page explains how the review skills establish base-branch context, validate truth, and avoid treating PR prose or model output as enough evidence.

## Mental model

| Layer                | What it proves                                                                                               |
| -------------------- | ------------------------------------------------------------------------------------------------------------ |
| Base truth           | what base branch does today, using SCSI when indexed or `git show <base>:<path>` plus local search otherwise |
| Change truth         | what the branch/PR actually does, using local diff plus file reads                                           |
| Assumption tests     | the smallest safe experiment that could disprove the review decision                                         |
| State-machine checks | ordered/stateful behavior matches an independent model or table before final/merge-ready claims              |
| Quality gates        | lint/type_check/tests trio after code was changed as part of an iteration cycle                              |

## Using it

### Base-branch context and semantic search

Review skills require comparing your local diff/PR against how base, usually `main`, works today.

If semantic code search (SCSI) is available and the current repo is indexed, it is required for base-branch context:

- Preflight is blocking: run `list_indices` first. Do not guess an index; try both `scsi-main` and `scsi-local` when both exist.
- If the user provided an index name, still run `list_indices` and verify the index exists before using it.
- If the user did not provide an index name, use the single obvious repo-matching index from `list_indices`; ask only when multiple equally plausible matches remain after evidence-based filtering.
- Use SCSI results as base-branch context only; validate the actual change via local git diffs and file reads.

Review outputs include one reviewer-metadata line so it is obvious what was used for base context:

```text
Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<scope>
```

`<scope>` is the actual diff under review, such as `<base>...HEAD`, `--cached`, `working-tree`, or `--cached + working-tree`.

Do not paste that line into GitHub comment bodies.

### Truth validation loop

For non-trivial review decisions — accepting a suggestion, pushing back, or proposing an alternative — use a strict verify-first loop:

1. Establish base truth: what base branch does today.
2. Establish change truth: what the branch/PR actually does.
3. Test assumptions: reproduce in `/tmp` when possible; otherwise run the smallest safe experiment in the worktree.
4. Check state machines: for reviewed behavior that is stateful, parser-like, branch-heavy, or ordered-condition dependent, build or inspect a `/tmp/state-machine-verification/<pwd>/<topic>/<slug>/` harness before calling the change final, merge-ready, or a review concern resolved.
5. Run quality gates: if you changed code as part of an iteration cycle, re-run the repo's lint/type_check/tests trio. Discover the correct commands from the repo; do not guess.

## Reference: skill support

Review modes live under `~/.agents/skills/k-review/references/`.

| File               | Owns                                                                                                                                                                                      |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `judging_core.md`  | truth validation, state-machine gate, deletion safety, historical rationale, product-flow lens, signal-quality gate, systemic-risk checks, coverage checklist, severity, post-review lens |
| `shared_rules.md`  | PR/SCSI/GitHub delivery rules, base-context gate, pending-review semantics, posting boundary                                                                                              |
| `pr_common.md`     | PR resolution, GitHub intake, ambient topic exploration, PR necessity/correctly-open audit, media evidence, anchoring                                                                     |
| `local_changes.md` | local diff / branch-delta review                                                                                                                                                          |
| `pr_review.md`     | initial or continued PR review                                                                                                                                                            |
| `pr_fix.md`        | address reviewer feedback                                                                                                                                                                 |
| `plan_review.md`   | plan/design-doc review against codebase reality before implementation                                                                                                                     |

## Internals (for maintainers)

### PR and issue intake

The PR/issue intake gate is deliberately exhaustive:

- PR and issue descriptions/bodies line by line.
- every conversation comment, review body, review comment, thread, and reply.
- every image/GIF/video or attachment.
- recursively discovered PR/issue/comment/media/link references until no reachable relevant reference remains unread.

GitHub posting and PR/issue composition skills reuse the same gate when output depends on existing PR/issue/comment context.

### Pending-review awareness

Pending-review awareness is part of the PR-mode gate:

1. list reviews for the PR.
2. select current-account `state == PENDING` reviews.
3. read draft comments.
4. compare with submitted comments/replies by the same account.
5. include `Pending review reconciliation:` in output.

That lets a later posting session reuse, merge, replace, or drop previous-session feedback instead of creating a competing review.

### Ambient topic exploration

For disagreements or missing rationale, the review skill adds bounded **Ambient Topic Exploration**:

- build a topic map.
- search related GitHub issues/PRs.
- search GitHub Discussions via GraphQL `SearchType.DISCUSSION`.
- search Slack MCP public/team channels when available.
- read high-signal hits with the same intake rules.

Skip it for routine reviews where direct context and base-branch context are enough.

### PR necessity and correctly-open audit

For other-authored or unknown-author PRs, the multi-agent flow runs a blocking **PR Necessity + Correctly-Open Audit** before implementation review.

It classifies:

- author intent.
- whether the PR is procedurally correctly open.
- whether the work is still needed.
- whether similar cross-cutting work is already open or recently merged.

Slack evidence is used only when Slack tools are available. Private channels/DMs require explicit consent.
