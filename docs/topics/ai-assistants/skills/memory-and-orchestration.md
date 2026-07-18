---
sidebar_position: 3
title: Memory and orchestration
---

# Memory and orchestration

These skills coordinate long-running agent work, durable learning, and user-intent discovery.

## `k-ai-kb`

| Field    | Value                                                                            |
| -------- | -------------------------------------------------------------------------------- |
| Use when | recalling or persisting durable cross-session knowledge via `,ai-kb`             |
| Source   | [`exact_k-ai-kb`](../../../../home/exact_dot_agents/exact_skills/exact_k-ai-kb/) |
| Related  | [Agent memory](../knowledge-base/index.md)                                       |

## `k-proof`

| Field    | Value                                                                                                                                        |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | explicit proof/receipt requests, handoffs, risky/runtime claims, failed attempts, blockers, or multi-evidence freeform changes need a ledger |
| Source   | [`exact_k-proof`](../../../../home/exact_dot_agents/exact_skills/exact_k-proof/)                                                             |
| CLI      | `,proof` stores proof state outside worktrees under `$AGENT_PROOF_HOME`, `$XDG_STATE_HOME`, or `~/.local/state`                              |

`k-proof` is available in two ways. Explicit requests route through the skill frontmatter and `SKILL.md`. Ordinary non-review/non-build iteration gets the same hard-trigger rule from the always-on SOP plus the shared verification prefix injected by session hooks, Pi, tmux prompt wrapping, and subagent profile templates. Both paths use the same boundary: start a `,proof` ledger only for hard-triggered freeform claims; use inline anchors for simple or single-evidence work.

## `k-palantir`

| Field    | Value                                                                                                                            |
| -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Use when | the user explicitly asks to use Palantír, summon a legion, operate an existing legion, or open the seeing-stone dashboard        |
| Routing  | model-invoked only after that explicit user intent; ordinary task size, complexity, or instructions to continue never trigger it |
| Source   | [`exact_k-palantir`](../../../../home/exact_dot_agents/exact_skills/exact_k-palantir/)                                           |
| Related  | [Palantír orchestrator](../palantir.md)                                                                                          |

## `k-interview-me`

| Field    | Value                                                                                          |
| -------- | ---------------------------------------------------------------------------------------------- |
| Use when | reverse-interviewing the user until intent is fully clear                                      |
| Source   | [`exact_k-interview-me`](../../../../home/exact_dot_agents/exact_skills/exact_k-interview-me/) |
| Routing  | manual                                                                                         |

## `k-spec`

| Field    | Value                                                                                                                                                |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | developing an idea, feature request, or bug into a spec packet with red-capable acceptance checks                                                    |
| Source   | [`exact_k-spec`](../../../../home/exact_dot_agents/exact_skills/exact_k-spec/)                                                                       |
| Output   | packet at `/tmp/specs/<pwd>/<topic>.spec.md`; consumers: `/k-build`, `,palantir summon --criteria`, `k-compose-issue` issue text/packet, plan review |

Fork-closing consults a domain overlay's planning fork checklist when the verified target repo has one (currently `k-elastic-domain` for `elastic/kibana`). Forks that cannot close locally (external sign-off, another team's decision) go in the packet's `External dependencies` section — owner, blocked criteria, recommended default — instead of blocking assembly; consumers must not start blocked criteria.

## `k-build`

| Field    | Value                                                                                                            |
| -------- | ---------------------------------------------------------------------------------------------------------------- |
| Use when | hands-free in-session implementation of an approved spec packet (two human gates: packet approval, final report) |
| Source   | [`exact_k-build`](../../../../home/exact_dot_agents/exact_skills/exact_k-build/)                                 |
| Routing  | manual                                                                                                           |
| Related  | criteria ledger + adversarial criteria-verifier lane; detached sibling is `,palantir summon --criteria`          |

## `k-text-tournament`

| Field    | Value                                                                                                                                              |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | automatically comparing three plausible edits before a material human-maintained prose rewrite                                                     |
| Source   | [`exact_k-text-tournament`](../../../../home/exact_dot_agents/exact_skills/exact_k-text-tournament/)                                               |
| Routing  | model-invoked                                                                                                                                      |
| Boundary | interactive turns use only a cross-family two-order winner; detached orchestration relies on its scheduled review stages instead of a nested judge |

## `k-improve-local`

| Field    | Value                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------ |
| Use when | proposing one evidence-backed improvement to local changes                                       |
| Source   | [`exact_k-improve-local`](../../../../home/exact_dot_agents/exact_skills/exact_k-improve-local/) |
| Routing  | manual                                                                                           |

## `k-improve-branch`

| Field    | Value                                                                                              |
| -------- | -------------------------------------------------------------------------------------------------- |
| Use when | proposing one evidence-backed improvement to the current branch, PR, or issue goal                 |
| Source   | [`exact_k-improve-branch`](../../../../home/exact_dot_agents/exact_skills/exact_k-improve-branch/) |
| Routing  | manual                                                                                             |

## `k-improve-targeted`

| Field    | Value                                                                                                  |
| -------- | ------------------------------------------------------------------------------------------------------ |
| Use when | proposing one evidence-backed improvement to a targeted codebase area                                  |
| Source   | [`exact_k-improve-targeted`](../../../../home/exact_dot_agents/exact_skills/exact_k-improve-targeted/) |
| Routing  | manual                                                                                                 |

## `k-improve-codebase`

| Field    | Value                                                                                                  |
| -------- | ------------------------------------------------------------------------------------------------------ |
| Use when | proposing one evidence-backed improvement to the whole codebase                                        |
| Source   | [`exact_k-improve-codebase`](../../../../home/exact_dot_agents/exact_skills/exact_k-improve-codebase/) |
| Routing  | manual                                                                                                 |
