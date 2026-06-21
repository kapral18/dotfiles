---
sidebar_position: 2
title: Base context and truth validation
---

# Base context and truth validation

## Base-branch context and semantic search

Review skills require comparing your local diff/PR against how base (usually `main`) works today.

If semantic code search (SCSI) is available and the current repo is indexed, it is required for base-branch context:

- Preflight is blocking: run `list_indices` first (do not guess an index; try both `scsi-main` and `scsi-local` when both exist).
- If the user provided an index name, still run `list_indices` and verify the index exists before using it.
- If the user did not provide an index name, use the single obvious repo-matching index from `list_indices`; ask only when multiple equally plausible matches remain after evidence-based filtering.
- Use SCSI results as base-branch context only; validate the actual change via local git diffs and file reads.

Review outputs also include a single reviewer-metadata line so it's obvious what was used for base context:

```text
Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<scope>
```

`<scope>` is the actual diff under review, such as `<base>...HEAD`, `--cached`, `working-tree`, or `--cached + working-tree`.

Do not paste that line into GitHub comment bodies.

## Truth validation loop

For non-trivial review decisions (accepting a suggestion, pushing back, or proposing an alternative), use a strict verify-first loop:

- Base truth: establish what base branch does today (SCSI when indexed; otherwise `git show <base>:<path>` + local search).
- Change truth: validate what your branch/PR actually does (local diff + file reads).
- Assumption tests: reproduce in `/tmp` when possible; otherwise run the smallest safe experiment in the worktree.
- State-machine checks: for reviewed behavior that is stateful, parser-like, branch-heavy, or ordered-condition dependent, build or inspect a `/tmp/state-machine-verification/<pwd>/<topic>/<slug>/` harness before calling the change final, merge-ready, or a review concern resolved.
- Quality gates: if you changed code as part of an iteration cycle, re-run the repo's lint/type_check/tests trio (discover the correct commands from the repo; do not guess).

Skill support:

Review modes live under `~/.agents/skills/review/references/`:

| File               | Owns                                                                                                                        |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| `judging_core.md`  | truth validation, state-machine gate, deletion safety, historical rationale, coverage checklist, severity, post-review lens |
| `shared_rules.md`  | PR/SCSI/GitHub delivery rules, base-context gate, pending-review semantics, posting boundary                                |
| `pr_common.md`     | PR resolution, GitHub intake, ambient topic exploration, PR necessity/correctly-open audit, media evidence, anchoring       |
| `local_changes.md` | local diff / branch-delta review                                                                                            |
| `pr_review.md`     | initial or continued PR review                                                                                              |
| `pr_fix.md`        | address reviewer feedback                                                                                                   |

The PR/issue intake gate is deliberately exhaustive:

- PR and issue descriptions/bodies line by line.
- every conversation comment, review body, review comment, thread, and reply.
- every image/GIF/video or attachment.
- recursively discovered PR/issue/comment/media/link references until no reachable relevant reference remains unread.

GitHub posting and PR/issue composition skills reuse the same gate when output depends on existing PR/issue/comment context.

Pending-review awareness is part of the PR-mode gate:

1. list reviews for the PR.
2. select current-account `state == PENDING` reviews.
3. read draft comments.
4. compare with submitted comments/replies by the same account.
5. include `Pending review reconciliation:` in output.

That lets a later posting session reuse, merge, replace, or drop previous-session feedback instead of creating a competing review.

For disagreements or missing rationale, the review skill adds bounded **Ambient Topic Exploration**:

- build a topic map.
- search related GitHub issues/PRs.
- search GitHub Discussions via GraphQL `SearchType.DISCUSSION`.
- search Slack MCP public/team channels when available.
- read high-signal hits with the same intake rules.

Skip it for routine reviews where direct context and base-branch context are enough.

For other-authored or unknown-author PRs, the multi-agent flow runs a blocking **PR Necessity + Correctly-Open Audit** before implementation review.

It classifies:

- author intent.
- whether the PR is procedurally correctly open.
- whether the work is still needed.
- whether similar cross-cutting work is already open or recently merged.

Slack evidence is used only when Slack tools are available; private channels/DMs require explicit consent.
