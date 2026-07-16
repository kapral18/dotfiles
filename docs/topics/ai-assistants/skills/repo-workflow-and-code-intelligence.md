---
sidebar_position: 2
title: Repo workflow and code intelligence
---

# Repo workflow and code intelligence

These skills operate on local repositories, code search, cleanup, and external source inspection.

## `k-code-quality`

| Field    | Value                                                                                          |
| -------- | ---------------------------------------------------------------------------------------------- |
| Use when | editing, reviewing, or refactoring implementation code in any language                         |
| Source   | [`exact_k-code-quality`](../../../../home/exact_dot_agents/exact_skills/exact_k-code-quality/) |
| Boundary | style and maintainability details only; SOP owns compatibility, scope, and verification gates  |

`k-code-quality` routes to narrower skills when the surface is present: `k-code-quality-react` for React/JSX/TSX/hooks, `k-code-quality-tests` for tests/fixtures/assertions, and `k-code-quality-web` for HTML/CSS/accessibility/browser UI.

## `k-code-quality-react`

| Field    | Value                                                                                                      |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| Use when | editing React, JSX, TSX, hooks, components, props, state, effects, or client-side UI behavior              |
| Source   | [`exact_k-code-quality-react`](../../../../home/exact_dot_agents/exact_skills/exact_k-code-quality-react/) |

## `k-code-quality-tests`

| Field    | Value                                                                                                      |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| Use when | adding, editing, reviewing, or debugging tests, fixtures, mocks, snapshots, assertions, or coverage        |
| Source   | [`exact_k-code-quality-tests`](../../../../home/exact_dot_agents/exact_skills/exact_k-code-quality-tests/) |

## `k-code-quality-web`

| Field    | Value                                                                                                  |
| -------- | ------------------------------------------------------------------------------------------------------ |
| Use when | editing HTML, CSS, DOM markup, layout, responsive styles, accessibility, or browser UI                 |
| Source   | [`exact_k-code-quality-web`](../../../../home/exact_dot_agents/exact_skills/exact_k-code-quality-web/) |

## `k-codebase-design`

| Field    | Value                                                                                                |
| -------- | ---------------------------------------------------------------------------------------------------- |
| Use when | designing a module interface, deciding a seam, deepening a module, or making code testable           |
| Source   | [`exact_k-codebase-design`](../../../../home/exact_dot_agents/exact_skills/exact_k-codebase-design/) |
| Boundary | design vocabulary only; SOP owns compatibility/scope; `k-code-quality` owns implementation style     |
| Pivots   | receives `k-diagnosing-bugs` architectural handoffs; hands to `k-code-quality-tests` once settled    |

## `k-diagnosing-bugs`

| Field    | Value                                                                                                       |
| -------- | ----------------------------------------------------------------------------------------------------------- |
| Use when | diagnosing a hard bug, failure, flake, or performance regression — build a tight red loop first             |
| Source   | [`exact_k-diagnosing-bugs`](../../../../home/exact_dot_agents/exact_skills/exact_k-diagnosing-bugs/)        |
| Boundary | routes into SOP §3.4/§3.5 gates; not the runtime-truth chain for "is X set up right"                        |
| Pivots   | no-correct-seam / architectural post-mortem → `k-codebase-design`; regression test → `k-code-quality-tests` |

## `k-prototype`

| Field    | Value                                                                                           |
| -------- | ----------------------------------------------------------------------------------------------- |
| Use when | building throwaway code to answer a design question (logic/state model, or what a UI should be) |
| Source   | [`exact_k-prototype`](../../../../home/exact_dot_agents/exact_skills/exact_k-prototype/)        |
| Boundary | explicit throwaway exception to artifact necessity; delete or absorb when done                  |
| Pivots   | closes `k-spec` empirical forks — the verdict returns to the packet's Context line              |

## `k-git`

| Field    | Value                                                                                      |
| -------- | ------------------------------------------------------------------------------------------ |
| Use when | local git operations: status/diff/log, branching, committing, pushing, rebasing, conflicts |
| Source   | [`exact_k-git`](../../../../home/exact_dot_agents/exact_skills/exact_k-git/)               |
| Boundary | no GitHub side effects; no worktree management                                             |

## `k-worktrees`

| Field      | Value                                                                                    |
| ---------- | ---------------------------------------------------------------------------------------- |
| Use when   | `,w`, `,gh-worktree`, PR/issue worktrees, listing/pruning/removing worktrees             |
| Source     | [`exact_k-worktrees`](../../../../home/exact_dot_agents/exact_skills/exact_k-worktrees/) |
| Preference | prefer `,w` / `,gh-worktree` over raw `git worktree`                                     |

## `k-tmux`

| Field    | Value                                                                                        |
| -------- | -------------------------------------------------------------------------------------------- |
| Use when | running, probing, or automating tmux commands, panes, sessions, sockets, or interactive CLIs |
| Source   | [`exact_k-tmux`](../../../../home/exact_dot_agents/exact_skills/exact_k-tmux/)               |
| Boundary | never mutate the default tmux server unless the current target is verified or user-requested |

## `k-semantic-code-search`

| Field    | Value                                                                                                          |
| -------- | -------------------------------------------------------------------------------------------------------------- |
| Use when | SCSI semantic search, base-branch context, verifying/selecting a semantic index                                |
| Source   | [`exact_k-semantic-code-search`](../../../../home/exact_dot_agents/exact_skills/exact_k-semantic-code-search/) |
| Boundary | not durable memory; use [Agent memory](../knowledge-base/index.md) for that                                    |

## `k-sem` skill (`,sem` CLI)

| Field    | Value                                                                        |
| -------- | ---------------------------------------------------------------------------- |
| Use when | entity-level git diff, blame, impact analysis, dependency graphs             |
| Source   | [`exact_k-sem`](../../../../home/exact_dot_agents/exact_skills/exact_k-sem/) |
| Tool     | `,sem` CLI                                                                   |

## `k-weave`

| Field    | Value                                                                            |
| -------- | -------------------------------------------------------------------------------- |
| Use when | preparing merges, previewing/resolving conflicts at function/class granularity   |
| Source   | [`exact_k-weave`](../../../../home/exact_dot_agents/exact_skills/exact_k-weave/) |
| Tool     | `weave` CLI                                                                      |

## `k-research`

| Field    | Value                                                                                  |
| -------- | -------------------------------------------------------------------------------------- |
| Use when | inspecting a public GitHub repo/library/tool source to answer how it works             |
| Source   | [`exact_k-research`](../../../../home/exact_dot_agents/exact_skills/exact_k-research/) |
| Boundary | source-first repo inspection, not generic web browsing                                 |

## `k-jscpd`

| Field    | Value                                                                            |
| -------- | -------------------------------------------------------------------------------- |
| Use when | duplicate-code detection during refactor or cleanup                              |
| Source   | [`exact_k-jscpd`](../../../../home/exact_dot_agents/exact_skills/exact_k-jscpd/) |
| Tool     | `jscpd`                                                                          |

## `k-knip`

| Field    | Value                                                                          |
| -------- | ------------------------------------------------------------------------------ |
| Use when | unused files, dependencies, and exports in JS/TS projects                      |
| Source   | [`exact_k-knip`](../../../../home/exact_dot_agents/exact_skills/exact_k-knip/) |
| Tool     | `knip`                                                                         |

## `k-cli-skills`

| Field    | Value                                                                                      |
| -------- | ------------------------------------------------------------------------------------------ |
| Use when | creating or upgrading CLI tool skills                                                      |
| Source   | [`exact_k-cli-skills`](../../../../home/exact_dot_agents/exact_skills/exact_k-cli-skills/) |
| Boundary | CLI-tool skill mechanics; general skill craft lives in `k-writing-great-skills`            |

## `k-writing-great-skills`

| Field    | Value                                                                                                          |
| -------- | -------------------------------------------------------------------------------------------------------------- |
| Use when | authoring or refactoring any skill: invocation choice, information hierarchy, leading words, pruning           |
| Source   | [`exact_k-writing-great-skills`](../../../../home/exact_dot_agents/exact_skills/exact_k-writing-great-skills/) |
| Routing  | model-invoked; auto-loads when authoring/refactoring a skill                                                   |
| Boundary | general skill craft; `k-cli-skills` owns CLI-tool-specific mechanics                                           |

## `k-walkthrough`

| Field    | Value                                                                                        |
| -------- | -------------------------------------------------------------------------------------------- |
| Use when | interactive codebase exploration, architecture tracing, diagrams                             |
| Source   | [`exact_k-walkthrough`](../../../../home/exact_dot_agents/exact_skills/exact_k-walkthrough/) |
| Routing  | manual                                                                                       |
