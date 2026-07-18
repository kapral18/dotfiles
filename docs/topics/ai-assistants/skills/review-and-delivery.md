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

## `k-agent-review`

| Field    | Value                                                                                          |
| -------- | ---------------------------------------------------------------------------------------------- |
| Use when | multi-agent review orchestration, reviewer fan-out, findings aggregation                       |
| Source   | [`exact_k-agent-review`](../../../../home/exact_dot_agents/exact_skills/exact_k-agent-review/) |
| Routing  | manual                                                                                         |
| Related  | [Agent-review topology](../reviews/agent-review-topology.md)                                   |

The controller now materializes a read-only context pack before fan-out and puts its path plus `head_sha` in every worker scope packet. Workers load `context-pack.md`, verify the manifest freshness gate, and report `pack_used`, `pack_stale`, or `pack_missing` instead of re-fetching PR artifacts already present in the pack.

After lane merge/dedup, adversarial verification and applicable `live-ui-review` run concurrently. Findings audit reconciles both outputs, and any UI evidence attached to refuted candidates is discarded as moot.

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

PR creation and edits are human-visible publication flows. The skill requires full context intake before composition, an explicit publication preflight ledger for title/body/Test Plan/metadata, user approval for invented human-visible text, and read-back comparison after `gh pr create` or `gh pr edit`. Review-comment posting preserves review-side UI evidence attachments in the approval/preflight handoff, including folder-open/provided status, md5s, dimensions, and controller image-QA status, while keeping local screenshot paths out of GitHub bodies.

Requested local-file uploads use the destination repository's web editor because the API cannot create `user-attachments` assets. The browser flow preserves existing draft text, treats attachment visibility as repository-scoped, and keeps embedding behind the publication gate. Pre-upload QA views every file, checks pairwise-distinct md5s, and rejects missing, empty, or dimensionally implausible images before upload.

## `k-compose-pr`

| Field    | Value                                                                                      |
| -------- | ------------------------------------------------------------------------------------------ |
| Use when | drafting PR title/body or publication packet before creating or editing a PR               |
| Source   | [`exact_k-compose-pr`](../../../../home/exact_dot_agents/exact_skills/exact_k-compose-pr/) |
| Boundary | draft + publication packet only; no GitHub side effects                                    |

When a draft feeds a GitHub side effect, it carries a PR publication packet outside the PR body so `k-github` can verify template compliance, screenshot proof status, linked issue intake, Test Plan completeness, metadata status, and unresolved placeholders before publishing. If the effort already has a `,proof` receipt, `k-compose-pr` treats it as completion proof only when its status is allowed, finalized, and sealed intact. A failing, incomplete, or broken ledger is surfaced, never retroactively completed during PR composition; independently verified Test Plan evidence remains usable.

When the change embodies decisions with observable consequences for others (API shape, privilege model, error responses, defaults), the body carries a `## Decisions` section — one bullet per decision with the risk if it was the wrong call; internal implementation choices are excluded (decision-log discipline adapted from [`elastic/plan`](https://github.com/elastic/plan)).

## `k-compose-issue`

| Field    | Value                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------ |
| Use when | drafting issue title/body or publication packet before creating or editing an issue              |
| Source   | [`exact_k-compose-issue`](../../../../home/exact_dot_agents/exact_skills/exact_k-compose-issue/) |
| Boundary | draft + publication packet only; no GitHub side effects                                          |

When a draft feeds a GitHub issue side effect, it carries an issue publication packet outside the issue body so `k-github` can verify GitHub issue type, metadata, duplicate checks, parent/sub-issue links, intake, approval, and read-back before publishing.

## `k-communication`

| Field    | Value                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------ |
| Use when | wording anything another human will read                                                         |
| Source   | [`exact_k-communication`](../../../../home/exact_dot_agents/exact_skills/exact_k-communication/) |
| Boundary | governs wording, not whether publishing is allowed                                               |

## `k-present-pr`

| Field    | Value                                                                                      |
| -------- | ------------------------------------------------------------------------------------------ |
| Use when | building an HTML scrollytelling walkthrough of a PR or local diff                          |
| Source   | [`exact_k-present-pr`](../../../../home/exact_dot_agents/exact_skills/exact_k-present-pr/) |
| Routing  | manual                                                                                     |
