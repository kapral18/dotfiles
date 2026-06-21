---
sidebar_position: 4
title: Elastic and Kibana
---

# Elastic and Kibana

These skills are gated to Elastic/Kibana contexts and layer domain policy over generic workflows.

## `elastic-domain`

| Field    | Value                                                                                          |
| -------- | ---------------------------------------------------------------------------------------------- |
| Use when | Elastic/Kibana overlay for PRs, labels, ownership, bots, Buildkite, live UI                    |
| Source   | [`exact_elastic-domain`](../../../../home/exact_dot_agents/exact_skills/exact_elastic-domain/) |
| Boundary | propose-only unless the active primary skill permits side effects                              |

## `buildkite`

| Field    | Value                                                                                |
| -------- | ------------------------------------------------------------------------------------ |
| Use when | Buildkite status, logs, pipelines, debug, or any `buildkite.com` URL                 |
| Source   | [`exact_buildkite`](../../../../home/exact_dot_agents/exact_skills/exact_buildkite/) |
| Gate     | elastic org repos                                                                    |

## `kibana-labels-propose`

| Field    | Value                                                                                                        |
| -------- | ------------------------------------------------------------------------------------------------------------ |
| Use when | proposing labels, backports, or version targets for Kibana PRs/issues                                        |
| Source   | [`exact_kibana-labels-propose`](../../../../home/exact_dot_agents/exact_skills/exact_kibana-labels-propose/) |
| Boundary | propose-only                                                                                                 |

## `kibana-management-ownership`

| Field    | Value                                                                                                                    |
| -------- | ------------------------------------------------------------------------------------------------------------------------ |
| Use when | determining Kibana ownership/reviewer targeting via CODEOWNERS                                                           |
| Source   | [`exact_kibana-management-ownership`](../../../../home/exact_dot_agents/exact_skills/exact_kibana-management-ownership/) |
| Boundary | propose-only                                                                                                             |

## `kibana-console-monaco`

| Field    | Value                                                                                                        |
| -------- | ------------------------------------------------------------------------------------------------------------ |
| Use when | automating/testing Kibana Dev Tools Console Monaco editor                                                    |
| Source   | [`exact_kibana-console-monaco`](../../../../home/exact_dot_agents/exact_skills/exact_kibana-console-monaco/) |
| Gate     | `elastic/kibana` repos                                                                                       |

## `kbn-backport`

| Field    | Value                                                                                      |
| -------- | ------------------------------------------------------------------------------------------ |
| Use when | running an end-to-end Kibana backport workflow                                             |
| Source   | [`exact_kbn-backport`](../../../../home/exact_dot_agents/exact_skills/exact_kbn-backport/) |
| Routing  | manual                                                                                     |

## `standup`

| Field    | Value                                                                            |
| -------- | -------------------------------------------------------------------------------- |
| Use when | preparing/posting a Kibana management standup update after approval              |
| Source   | [`exact_standup`](../../../../home/exact_dot_agents/exact_skills/exact_standup/) |
| Routing  | manual                                                                           |
