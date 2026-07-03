---
sidebar_position: 2
title: Repo workflow and code intelligence
---

# Repo workflow and code intelligence

These skills operate on local repositories, code search, cleanup, and external source inspection.

## `code-quality`

| Field    | Value                                                                                         |
| -------- | --------------------------------------------------------------------------------------------- |
| Use when | editing, reviewing, or refactoring implementation code in any language                        |
| Source   | [`exact_code-quality`](../../../../home/exact_dot_agents/exact_skills/exact_code-quality/)    |
| Boundary | style and maintainability details only; SOP owns compatibility, scope, and verification gates |

`code-quality` routes to narrower skills when the surface is present: `code-quality-react` for React/JSX/TSX/hooks, `code-quality-tests` for tests/fixtures/assertions, and `code-quality-web` for HTML/CSS/accessibility/browser UI.

## `code-quality-react`

| Field    | Value                                                                                                  |
| -------- | ------------------------------------------------------------------------------------------------------ |
| Use when | editing React, JSX, TSX, hooks, components, props, state, effects, or client-side UI behavior          |
| Source   | [`exact_code-quality-react`](../../../../home/exact_dot_agents/exact_skills/exact_code-quality-react/) |

## `code-quality-tests`

| Field    | Value                                                                                                  |
| -------- | ------------------------------------------------------------------------------------------------------ |
| Use when | adding, editing, reviewing, or debugging tests, fixtures, mocks, snapshots, assertions, or coverage    |
| Source   | [`exact_code-quality-tests`](../../../../home/exact_dot_agents/exact_skills/exact_code-quality-tests/) |

## `code-quality-web`

| Field    | Value                                                                                              |
| -------- | -------------------------------------------------------------------------------------------------- |
| Use when | editing HTML, CSS, DOM markup, layout, responsive styles, accessibility, or browser UI             |
| Source   | [`exact_code-quality-web`](../../../../home/exact_dot_agents/exact_skills/exact_code-quality-web/) |

## `codebase-design`

| Field    | Value                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------ |
| Use when | designing a module interface, deciding a seam, deepening a module, or making code testable       |
| Source   | [`exact_codebase-design`](../../../../home/exact_dot_agents/exact_skills/exact_codebase-design/) |
| Boundary | design vocabulary only; SOP owns compatibility/scope; `code-quality` owns implementation style   |
| Pivots   | receives `diagnosing-bugs` architectural handoffs; hands to `code-quality-tests` once settled    |

## `diagnosing-bugs`

| Field    | Value                                                                                                   |
| -------- | ------------------------------------------------------------------------------------------------------- |
| Use when | diagnosing a hard bug, failure, flake, or performance regression — build a tight red loop first         |
| Source   | [`exact_diagnosing-bugs`](../../../../home/exact_dot_agents/exact_skills/exact_diagnosing-bugs/)        |
| Boundary | routes into SOP §3.4/§3.5 gates; not the runtime-truth chain for "is X set up right"                    |
| Pivots   | no-correct-seam / architectural post-mortem → `codebase-design`; regression test → `code-quality-tests` |

## `prototype`

| Field    | Value                                                                                           |
| -------- | ----------------------------------------------------------------------------------------------- |
| Use when | building throwaway code to answer a design question (logic/state model, or what a UI should be) |
| Source   | [`exact_prototype`](../../../../home/exact_dot_agents/exact_skills/exact_prototype/)            |
| Boundary | explicit throwaway exception to artifact necessity; delete or absorb when done                  |
| Pivots   | closes `spec` empirical forks — the verdict returns to the packet's Context line                |

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

## `sem` skill (`,sem` CLI)

| Field    | Value                                                                    |
| -------- | ------------------------------------------------------------------------ |
| Use when | entity-level git diff, blame, impact analysis, dependency graphs         |
| Source   | [`exact_sem`](../../../../home/exact_dot_agents/exact_skills/exact_sem/) |
| Tool     | `,sem` CLI                                                               |

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
| Boundary | CLI-tool skill mechanics; general skill craft lives in `writing-great-skills`          |

## `writing-great-skills`

| Field    | Value                                                                                                      |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| Use when | authoring or refactoring any skill: invocation choice, information hierarchy, leading words, pruning       |
| Source   | [`exact_writing-great-skills`](../../../../home/exact_dot_agents/exact_skills/exact_writing-great-skills/) |
| Routing  | model-invoked; auto-loads when authoring/refactoring a skill                                               |
| Boundary | general skill craft; `cli-skills` owns CLI-tool-specific mechanics                                         |

## `walkthrough`

| Field    | Value                                                                                    |
| -------- | ---------------------------------------------------------------------------------------- |
| Use when | interactive codebase exploration, architecture tracing, diagrams                         |
| Source   | [`exact_walkthrough`](../../../../home/exact_dot_agents/exact_skills/exact_walkthrough/) |
| Routing  | manual                                                                                   |
