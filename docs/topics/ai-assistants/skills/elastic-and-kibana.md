---
sidebar_position: 4
title: Elastic and Kibana
---

# Elastic and Kibana

These skills are gated to Elastic/Kibana contexts and layer domain policy over generic workflows.

The boundary is intentional: generic skills (`k-review`, `k-agent-review`, `k-github`, `compose-*`) keep portable mechanics and gates; this page's skills own Elastic/Kibana labels, ownership, Buildkite routing, bot allowlists, PR templates, release-note rules, commit attribution, and Kibana live-UI target/data setup.

## `k-elastic-domain`

| Field    | Value                                                                                              |
| -------- | -------------------------------------------------------------------------------------------------- |
| Use when | Elastic/Kibana overlay for PRs, labels, ownership, bots, Buildkite, live UI                        |
| Source   | [`exact_k-elastic-domain`](../../../../home/exact_dot_agents/exact_skills/exact_k-elastic-domain/) |
| Boundary | propose-only unless the active primary skill permits side effects                                  |

The overlay also carries a Kibana planning fork checklist (`references/kibana-planning-forks.md`) that the generic `k-spec` skill consults when the target repo is `elastic/kibana`: API versioning, Saved Objects/migrations, privileges, dependencies, feature flags, backports, test placement, alerting, and instrumentation forks. Adapted from the specialist `elicitation_questions` in [`elastic/plan`](https://github.com/elastic/plan) (`prompts/teams/elastic-kibana/`); refresh it by re-reading that directory upstream and folding in changes — curated, not mirrored.

## `k-buildkite`

| Field    | Value                                                                                    |
| -------- | ---------------------------------------------------------------------------------------- |
| Use when | Buildkite status, logs, pipelines, debug, or any `buildkite.com` URL                     |
| Source   | [`exact_k-buildkite`](../../../../home/exact_dot_agents/exact_skills/exact_k-buildkite/) |
| Gate     | elastic org repos                                                                        |

## `k-kibana-labels-propose`

| Field    | Value                                                                                                            |
| -------- | ---------------------------------------------------------------------------------------------------------------- |
| Use when | proposing labels, backports, or version targets for Kibana PRs/issues                                            |
| Source   | [`exact_k-kibana-labels-propose`](../../../../home/exact_dot_agents/exact_skills/exact_k-kibana-labels-propose/) |
| Boundary | propose-only                                                                                                     |

## `k-kibana-management-ownership`

| Field    | Value                                                                                                                        |
| -------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Use when | determining Kibana ownership/reviewer targeting via CODEOWNERS                                                               |
| Source   | [`exact_k-kibana-management-ownership`](../../../../home/exact_dot_agents/exact_skills/exact_k-kibana-management-ownership/) |
| Boundary | propose-only                                                                                                                 |

## `k-kibana-console-monaco`

| Field    | Value                                                                                                            |
| -------- | ---------------------------------------------------------------------------------------------------------------- |
| Use when | automating/testing Kibana Dev Tools Console Monaco editor                                                        |
| Source   | [`exact_k-kibana-console-monaco`](../../../../home/exact_dot_agents/exact_skills/exact_k-kibana-console-monaco/) |
| Gate     | `elastic/kibana` repos                                                                                           |

## `k-kbn-stack`

| Field    | Value                                                                                    |
| -------- | ---------------------------------------------------------------------------------------- |
| Use when | starting, reusing, inspecting, or tearing down local Kibana ES+Kibana dev stacks         |
| Source   | [`exact_k-kbn-stack`](../../../../home/exact_dot_agents/exact_skills/exact_k-kbn-stack/) |
| Tool     | `,kbn-stack`                                                                             |
| Gate     | `elastic/kibana` repos                                                                   |

Detached `,kbn-stack --detach` starts record the Kibana process log as `kbn_log` in the registry. Kibana live-UI checks use that log for optimizer-bundle readiness; the ES `log` field is not optimizer evidence. Before reusing a ready registry entry, correlate it with recorded pids, slot-derived port listeners, and log paths. That check validates a registry entry; it does not license guessing arbitrary localhost targets.

## `k-kbn-backport`

| Field    | Value                                                                                          |
| -------- | ---------------------------------------------------------------------------------------------- |
| Use when | running an end-to-end Kibana backport workflow                                                 |
| Source   | [`exact_k-kbn-backport`](../../../../home/exact_dot_agents/exact_skills/exact_k-kbn-backport/) |
| Routing  | manual                                                                                         |

## `k-kbn-standup`

| Field    | Value                                                                                        |
| -------- | -------------------------------------------------------------------------------------------- |
| Use when | preparing a draft for the Admin UX daily update                                              |
| Scope    | accessible public, internal, and private Elastic repositories plus Slack/DMs                 |
| Format   | bare URLs; per-artifact icons; `:merged:` per merge; direct `:sdh:` summary tag              |
| Source   | [`exact_k-kbn-standup`](../../../../home/exact_dot_agents/exact_skills/exact_k-kbn-standup/) |
| Routing  | manual                                                                                       |
