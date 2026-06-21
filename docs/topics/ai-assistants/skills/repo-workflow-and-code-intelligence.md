---
sidebar_position: 2
title: Repo workflow and code intelligence
---

# Repo workflow and code intelligence

These skills operate on local repositories, code search, cleanup, and external source inspection.

## `git`

| Field    | Value                                                                                      |
| -------- | ------------------------------------------------------------------------------------------ |
| Use when | local git operations: status/diff/log, branching, committing, pushing, rebasing, conflicts |
| Source   | [`exact_git`](../../../../home/exact_dot_agents/exact_skills/exact_git/)                   |
| Boundary | no GitHub side effects; no worktree management                                             |

## `worktrees`

| Field      | Value                                                                                |
| ---------- | ------------------------------------------------------------------------------------ |
| Use when   | `,w`, `,gh-worktree`, PR/issue worktrees, listing/pruning/removing worktrees         |
| Source     | [`exact_worktrees`](../../../../home/exact_dot_agents/exact_skills/exact_worktrees/) |
| Preference | prefer `,w` / `,gh-worktree` over raw `git worktree`                                 |

## `semantic-code-search`

| Field    | Value                                                                                                      |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| Use when | SCSI semantic search, base-branch context, verifying/selecting a semantic index                            |
| Source   | [`exact_semantic-code-search`](../../../../home/exact_dot_agents/exact_skills/exact_semantic-code-search/) |
| Boundary | not durable memory; use [Agent memory](../knowledge-base/index.md) for that                                |

## `sem`

| Field    | Value                                                                      |
| -------- | -------------------------------------------------------------------------- |
| Use when | entity-level git diff, blame, impact analysis, token-budgeted code context |
| Source   | [`exact_sem`](../../../../home/exact_dot_agents/exact_skills/exact_sem/)   |
| Tool     | `sem` CLI                                                                  |

## `weave`

| Field    | Value                                                                          |
| -------- | ------------------------------------------------------------------------------ |
| Use when | preparing merges, previewing/resolving conflicts at function/class granularity |
| Source   | [`exact_weave`](../../../../home/exact_dot_agents/exact_skills/exact_weave/)   |
| Tool     | `weave` CLI                                                                    |

## `research`

| Field    | Value                                                                              |
| -------- | ---------------------------------------------------------------------------------- |
| Use when | inspecting a public GitHub repo/library/tool source to answer how it works         |
| Source   | [`exact_research`](../../../../home/exact_dot_agents/exact_skills/exact_research/) |
| Boundary | source-first repo inspection, not generic web browsing                             |

## `jscpd`

| Field    | Value                                                                        |
| -------- | ---------------------------------------------------------------------------- |
| Use when | duplicate-code detection during refactor or cleanup                          |
| Source   | [`exact_jscpd`](../../../../home/exact_dot_agents/exact_skills/exact_jscpd/) |
| Tool     | `jscpd`                                                                      |

## `knip`

| Field    | Value                                                                      |
| -------- | -------------------------------------------------------------------------- |
| Use when | unused files, dependencies, and exports in JS/TS projects                  |
| Source   | [`exact_knip`](../../../../home/exact_dot_agents/exact_skills/exact_knip/) |
| Tool     | `knip`                                                                     |

## `cli-skills`

| Field    | Value                                                                                  |
| -------- | -------------------------------------------------------------------------------------- |
| Use when | creating or upgrading CLI tool skills                                                  |
| Source   | [`exact_cli-skills`](../../../../home/exact_dot_agents/exact_skills/exact_cli-skills/) |
| Boundary | skill authoring, not normal tool usage                                                 |

## `walkthrough`

| Field    | Value                                                                                    |
| -------- | ---------------------------------------------------------------------------------------- |
| Use when | interactive codebase exploration, architecture tracing, diagrams                         |
| Source   | [`exact_walkthrough`](../../../../home/exact_dot_agents/exact_skills/exact_walkthrough/) |
| Routing  | manual                                                                                   |
