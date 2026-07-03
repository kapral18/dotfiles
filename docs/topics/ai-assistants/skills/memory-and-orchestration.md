---
sidebar_position: 3
title: Memory and orchestration
---

# Memory and orchestration

These skills coordinate long-running agent work, durable learning, and user-intent discovery.

## `ai-kb`

| Field    | Value                                                                        |
| -------- | ---------------------------------------------------------------------------- |
| Use when | recalling or persisting durable cross-session knowledge via `,ai-kb`         |
| Source   | [`exact_ai-kb`](../../../../home/exact_dot_agents/exact_skills/exact_ai-kb/) |
| Related  | [Agent memory](../knowledge-base/index.md)                                   |

## `ralph`

| Field    | Value                                                                        |
| -------- | ---------------------------------------------------------------------------- |
| Use when | spawning, steering, verifying, replanning, or attaching to `,ralph go` runs  |
| Source   | [`exact_ralph`](../../../../home/exact_dot_agents/exact_skills/exact_ralph/) |
| Related  | [Ralph orchestrator](../ralph/index.md)                                      |

## `interview-me`

| Field    | Value                                                                                      |
| -------- | ------------------------------------------------------------------------------------------ |
| Use when | reverse-interviewing the user until intent is fully clear                                  |
| Source   | [`exact_interview-me`](../../../../home/exact_dot_agents/exact_skills/exact_interview-me/) |
| Routing  | manual                                                                                     |

## `spec`

| Field    | Value                                                                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Use when | developing an idea, feature request, or bug into a spec packet with red-capable acceptance checks                                                |
| Source   | [`exact_spec`](../../../../home/exact_dot_agents/exact_skills/exact_spec/)                                                                       |
| Output   | packet at `/tmp/specs/<pwd>/<topic>.spec.md`; consumers: `/build`, `,ralph go --spec` (via its JSON handoff block), `compose-issue`, plan review |

Fork-closing consults a domain overlay's planning fork checklist when the verified target repo has one (currently `elastic-domain` for `elastic/kibana`). Forks that cannot close locally (external sign-off, another team's decision) go in the packet's `External dependencies` section — owner, blocked criteria, recommended default — instead of blocking assembly; consumers must not start blocked criteria.

## `build`

| Field    | Value                                                                                                            |
| -------- | ---------------------------------------------------------------------------------------------------------------- |
| Use when | hands-free in-session implementation of an approved spec packet (two human gates: packet approval, final report) |
| Source   | [`exact_build`](../../../../home/exact_dot_agents/exact_skills/exact_build/)                                     |
| Routing  | manual                                                                                                           |
| Related  | criteria ledger + adversarial criteria-verifier lane; detached sibling is `,ralph go --spec`                     |

## `improve-local`

| Field    | Value                                                                                        |
| -------- | -------------------------------------------------------------------------------------------- |
| Use when | proposing one evidence-backed improvement to local changes                                   |
| Source   | [`exact_improve-local`](../../../../home/exact_dot_agents/exact_skills/exact_improve-local/) |
| Routing  | manual                                                                                       |

## `improve-branch`

| Field    | Value                                                                                          |
| -------- | ---------------------------------------------------------------------------------------------- |
| Use when | proposing one evidence-backed improvement to the current branch, PR, or issue goal             |
| Source   | [`exact_improve-branch`](../../../../home/exact_dot_agents/exact_skills/exact_improve-branch/) |
| Routing  | manual                                                                                         |

## `improve-targeted`

| Field    | Value                                                                                              |
| -------- | -------------------------------------------------------------------------------------------------- |
| Use when | proposing one evidence-backed improvement to a targeted codebase area                              |
| Source   | [`exact_improve-targeted`](../../../../home/exact_dot_agents/exact_skills/exact_improve-targeted/) |
| Routing  | manual                                                                                             |

## `improve-codebase`

| Field    | Value                                                                                              |
| -------- | -------------------------------------------------------------------------------------------------- |
| Use when | proposing one evidence-backed improvement to the whole codebase                                    |
| Source   | [`exact_improve-codebase`](../../../../home/exact_dot_agents/exact_skills/exact_improve-codebase/) |
| Routing  | manual                                                                                             |
