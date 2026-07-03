---
sidebar_position: 1
title: Review and delivery
---

# Review and delivery

These skills govern review methodology, GitHub side effects, and human-readable text.

## `review`

| Field    | Value                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------ |
| Use when | reviewing local changes, PRs, or plan/design docs; continuing reviews; addressing review threads |
| Source   | [`exact_review`](../../../../home/exact_dot_agents/exact_skills/exact_review/)                   |
| Related  | [Review workflow](../reviews/index.md)                                                           |

## `agent-review`

| Field    | Value                                                                                      |
| -------- | ------------------------------------------------------------------------------------------ |
| Use when | multi-agent review orchestration, reviewer fan-out, findings aggregation                   |
| Source   | [`exact_agent-review`](../../../../home/exact_dot_agents/exact_skills/exact_agent-review/) |
| Routing  | manual                                                                                     |
| Related  | [Agent-review topology](../reviews/agent-review-topology.md)                               |

## `light-review`

| Field    | Value                                                                                        |
| -------- | -------------------------------------------------------------------------------------------- |
| Use when | proportional-depth in-place audit of low-risk self-authored changes                          |
| Source   | [`exact_light-review`](../../../../home/exact_dot_agents/exact_skills/exact_light-review/)   |
| Boundary | escalate to `review` for PRs, others' code, risky/stateful changes, or required base context |

## `github`

| Field    | Value                                                                               |
| -------- | ----------------------------------------------------------------------------------- |
| Use when | GitHub mutations via `gh`: PRs, issues, comments, reviews, labels, releases, merges |
| Source   | [`exact_github`](../../../../home/exact_dot_agents/exact_skills/exact_github/)      |
| Boundary | not for read-only review analysis or draft-only writing                             |

PR creation and edits are human-visible publication flows. The skill requires full context intake before composition, an explicit publication preflight ledger for title/body/Test Plan/metadata, user approval for invented human-visible text, and read-back comparison after `gh pr create` or `gh pr edit`.

## `compose-pr`

| Field    | Value                                                                                  |
| -------- | -------------------------------------------------------------------------------------- |
| Use when | drafting PR title/body before creating or editing a PR                                 |
| Source   | [`exact_compose-pr`](../../../../home/exact_dot_agents/exact_skills/exact_compose-pr/) |
| Boundary | text only; no GitHub side effects                                                      |

When a draft feeds a GitHub side effect, it carries a compact composition ledger outside the PR body so `github` can verify linked issue intake, Test Plan completeness, title source, metadata source, and unresolved placeholders before publishing.

When the change embodies decisions with observable consequences for others (API shape, privilege model, error responses, defaults), the body carries a `## Decisions` section — one bullet per decision with the risk if it was the wrong call; internal implementation choices are excluded (decision-log discipline adapted from [`elastic/plan`](https://github.com/elastic/plan)).

## `compose-issue`

| Field    | Value                                                                                        |
| -------- | -------------------------------------------------------------------------------------------- |
| Use when | drafting issue title/body before creating or editing an issue                                |
| Source   | [`exact_compose-issue`](../../../../home/exact_dot_agents/exact_skills/exact_compose-issue/) |
| Boundary | text only; no GitHub side effects                                                            |

## `communication`

| Field    | Value                                                                                        |
| -------- | -------------------------------------------------------------------------------------------- |
| Use when | wording anything another human will read                                                     |
| Source   | [`exact_communication`](../../../../home/exact_dot_agents/exact_skills/exact_communication/) |
| Boundary | governs wording, not whether publishing is allowed                                           |

## `present-pr`

| Field    | Value                                                                                  |
| -------- | -------------------------------------------------------------------------------------- |
| Use when | building an HTML scrollytelling walkthrough of a PR or local diff                      |
| Source   | [`exact_present-pr`](../../../../home/exact_dot_agents/exact_skills/exact_present-pr/) |
| Routing  | manual                                                                                 |
