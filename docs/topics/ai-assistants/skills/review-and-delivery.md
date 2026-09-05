---
sidebar_position: 1
title: Review and delivery
---

# Review and delivery

These skills govern review methodology, GitHub side effects, and human-readable text.

## `k-review`

| Field    | Value                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------ |
| Use when | reviewing local changes, PRs, or plan/design docs; continuing reviews; addressing review threads |
| Source   | [`exact_k-review`](../../../../home/exact_dot_agents/exact_skills/exact_k-review/)               |
| Related  | [Review workflow](../reviews/index.md)                                                           |

`k-review` keeps all applicability triggers in `judging_core.md` and loads `judging_state.md`, `judging_change.md`, or `judging_product.md` before the matching check. Delivery, fixes, and the fix-diff stage use `review_delivery.md`, `review_fixes.md`, and `review_post_stage.md`. Direct reviewer/refuter contracts permit the same required gate references while retaining their read-only role boundaries.

## `k-deep-review`

| Field    | Value                                                                                        |
| -------- | -------------------------------------------------------------------------------------------- |
| Use when | bounded deep-review orchestration, reviewer rostering, findings aggregation                  |
| Source   | [`exact_k-deep-review`](../../../../home/exact_dot_agents/exact_skills/exact_k-deep-review/) |
| Routing  | manual                                                                                       |
| Related  | [Deep-review topology](../reviews/deep-review-topology.md)                                   |

The controller now materializes a read-only context pack before fan-out and puts its path plus `head_sha` in every worker scope packet. Workers load `context-pack.md`, verify the manifest freshness gate, and report `pack_used`, `pack_stale`, or `pack_missing` instead of re-fetching PR artifacts already present in the pack.

The deep controller loads complete procedures at their owning phases through seven references: `route-scope`, `pr-necessity`, `reviewer-roster`, `findings-audit`, `adversarial-verification`, `judgment`, and `live-ui-validation`. Phase order, worker boundaries, action permissions, and completion gates remain in the entrypoint. Resume uses the existing ledger and current instructions; new evidence reopens affected phases.

After lane merge/dedup, applicable `k-agent-live-ui-review` runs first, then findings audit cleans the candidate set, then final adversarial verification tries to refute the audited findings and sweeps for what every lane missed. The sighted reviewer roster is bounded: one baseline lane for simple single-surface diffs, extra lanes only for scope-evidenced independent risk. Lenses, triggers, and checks come from `k-review/references/lanes.md`, and the controller pastes the selected entry into the packet so a lane never loads the catalog, the router, or the mode files.

Controller preflight includes task-shaped `,ai-kb search` recall; relevant capsule lessons are folded into scope packets. Closeout records durable lessons with `,ai-kb remember` or task anti-patterns with `,agent-memory note anti_pattern`. Worker lifecycle is supervised: delivery acknowledgements are not progress, request-too-large or empty turns mark a worker dead, follow-ups are budgeted, and worker prose numbers are treated as self-reports until independently verified. Any worker image used in a human-visible packet must be opened/viewed by the controller first.

## `k-light-review`

| Field    | Value                                                                                          |
| -------- | ---------------------------------------------------------------------------------------------- |
| Use when | proportional-depth in-place audit of low-risk self-authored changes                            |
| Source   | [`exact_k-light-review`](../../../../home/exact_dot_agents/exact_skills/exact_k-light-review/) |
| Boundary | escalate to `k-review` for PRs, others' code, risky/stateful changes, or required base context |

## `k-github`

| Field    | Value                                                                                          |
| -------- | ---------------------------------------------------------------------------------------------- |
| Use when | GitHub mutations: PRs, issues, comments, reviews, labels, releases, merges, attachment uploads |
| Source   | [`exact_k-github`](../../../../home/exact_dot_agents/exact_skills/exact_k-github/)             |
| Boundary | not for read-only review analysis or draft-only writing                                        |

PR creation and edits are human-visible publication flows. The skill requires full context intake before composition, an explicit publication preflight ledger for title/body/Test Plan/metadata, user approval for invented human-visible text, and read-back comparison after `gh pr create` or `gh pr edit`. Review-comment posting preserves review-side UI evidence attachments in the approval/preflight handoff, including md5s, dimensions, and controller image-QA status, while keeping local screenshot paths out of GitHub bodies. Keep PR reviewer fields unset; GitHub handles reviewer assignment automatically. Review submit bodies stay short: acknowledge the review outcome, and when inline comments exist, do not repeat their details. For immediate-team PR authors, clean reviews approve, findings below CRITICAL use comment review, and CRITICAL blockers request changes; outside or unknown-team authors use the normal severity ladder. Requested local-file uploads use the destination repository's web editor because the API cannot create `user-attachments` assets. The browser flow preserves existing draft text, treats attachment visibility as repository-scoped, and keeps embedding behind the publication gate. Pre-upload QA views every file, checks pairwise-distinct md5s, and rejects missing, empty, or dimensionally implausible images before upload.

## `k-pr-fix-loop`

| Field    | Value                                                                                                                                                                                                                                                                                                                           |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | working actionable PR review comments through critical assessment, fix, verify, commit, push, PR update, reply, and resolve, with no per-step approval                                                                                                                                                                          |
| Source   | [`exact_k-pr-fix-loop`](../../../../home/exact_dot_agents/exact_skills/exact_k-pr-fix-loop/)                                                                                                                                                                                                                                    |
| Routing  | manual (`disable-model-invocation: true`); invoke only on explicit user request for this loop                                                                                                                                                                                                                                   |
| Boundary | a bounded approval packet for this loop's normal effects only (scoped edits, verification, commit, force-with-lease push to the current PR branch, PR body updates, media uploads, review-thread replies/resolves) — does not authorize merging, rebasing, pulling/merging base, unrelated metadata changes, or broad refactors |

Thin wrapper that sequences `k-review` (`references/pr_fix.md` in Drain Mode), `k-code-quality`/`k-code-quality-tests`, `k-git`, and `k-github`.

## `k-compose-pr`

| Field    | Value                                                                                      |
| -------- | ------------------------------------------------------------------------------------------ |
| Use when | drafting PR title/body or publication packet before creating or editing a PR               |
| Source   | [`exact_k-compose-pr`](../../../../home/exact_dot_agents/exact_skills/exact_k-compose-pr/) |
| Boundary | draft + publication packet only; no GitHub side effects                                    |

When a draft feeds a GitHub side effect, it carries a PR publication packet outside the PR body so `k-github` can verify template compliance, screenshot proof status, linked issue intake, Test Plan completeness, metadata status, and unresolved placeholders before publishing. If the effort already has a `,proof` receipt, `k-compose-pr` treats it as completion proof only when its status is allowed, finalized, and sealed intact. A failing, incomplete, or broken ledger is surfaced, never retroactively completed during PR composition; independently verified Test Plan evidence remains usable. The Test Plan is reviewer-runnable: exact commands or manual repro steps with expected and observed results, verified before proposal, not a mirror of changed test files from the diff.

When the change embodies decisions with observable consequences for others (API shape, privilege model, error responses, defaults), the body carries a `## Decisions` section — one bullet per decision with the risk if it was the wrong call; internal implementation choices are excluded (decision-log discipline adapted from [`elastic/plan`](https://github.com/elastic/plan)).

## `k-compose-issue`

| Field    | Value                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------ |
| Use when | drafting issue title/body or publication packet before creating or editing an issue              |
| Source   | [`exact_k-compose-issue`](../../../../home/exact_dot_agents/exact_skills/exact_k-compose-issue/) |
| Boundary | draft + publication packet only; no GitHub side effects                                          |

When a draft feeds a GitHub issue side effect, it carries an issue publication packet outside the issue body so `k-github` can verify GitHub issue type, metadata, duplicate checks, parent/sub-issue links, intake, approval, and read-back before publishing.

## `k-communication`

| Field    | Value                                                                                                                                                                                                               |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | wording anything another human will read                                                                                                                                                                            |
| Source   | [`exact_k-communication`](../../../../home/exact_dot_agents/exact_skills/exact_k-communication/)                                                                                                                    |
| Boundary | governs wording, not whether publishing is allowed                                                                                                                                                                  |
| Owned    | Shared external-register rules live directly in the [`skill entrypoint`](../../../../home/exact_dot_agents/exact_skills/exact_k-communication/readonly_SKILL.md); the existing-thread procedure remains conditional |

The default message shape is three parts: the point in the first sentence, the doubt when one exists (the assumption you could not verify), and a short collaborative close (`wdyt` / `lmk`). That close is the default nicety and replaces longer warmth rather than stacking with it. Budgets are per artifact class (`≤40` thread reply, `≤80` comment, `≤200` description), tighter than SOP §5.2's task-class budgets; the terse in-session shape does not carry over, because external readers get direct and polite.

## `k-present-pr`

| Field    | Value                                                                                      |
| -------- | ------------------------------------------------------------------------------------------ |
| Use when | building an HTML scrollytelling walkthrough of a PR or local diff                          |
| Source   | [`exact_k-present-pr`](../../../../home/exact_dot_agents/exact_skills/exact_k-present-pr/) |
| Routing  | manual                                                                                     |

Read all of `authoring.md`. Run the bundled `scripts/template.py prepare TEMPLATE DRAFT` and read the entire editable draft before filling it. `render TEMPLATE DRAFT OUTPUT` restores the template's exact fixed CSS/JS into a self-contained presentation. Keep its reserved markers unchanged, render again after content edits, and run all static and browser checks on the final output before opening it for the user. The canonical template remains unchanged; the helper replaces only the fixed-code read/copy operation.

Marker validation rejects unknown raw editing comments while allowing HTML-escaped marker text in visible code examples.
