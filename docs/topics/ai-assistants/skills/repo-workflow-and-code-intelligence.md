---
sidebar_position: 2
title: Repo workflow and code intelligence
---

# Repo workflow and code intelligence

These skills operate on local repositories, code search, cleanup, external source inspection, and evidence-gated public research.

## `k-code-quality`

| Field    | Value                                                                                                        |
| -------- | ------------------------------------------------------------------------------------------------------------ |
| Use when | editing, reviewing, or refactoring implementation code or repository artifacts                               |
| Source   | [`exact_k-code-quality`](../../../../home/exact_dot_agents/exact_skills/exact_k-code-quality/)               |
| Boundary | implementation-quality details, including minimal edit-scope detail, artifact necessity, and semantic dedupe |

`k-code-quality` routes to narrower skills when the surface is present: `k-code-quality-react` for React/JSX/TSX/hooks, `k-code-quality-tests` for tests/fixtures/assertions, and `k-code-quality-web` for HTML/CSS/accessibility/browser UI. Non-code artifacts (config keys, template variables, generated files, instruction sentences, completions, docs) have readers too; the skill requires identifying them and their generated or rendered outputs before editing and updating them in the same change.

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

| Field    | Value                                                                                                                 |
| -------- | --------------------------------------------------------------------------------------------------------------------- |
| Use when | designing a module interface, deciding a seam, deepening a module, or making code testable                            |
| Source   | [`exact_k-codebase-design`](../../../../home/exact_dot_agents/exact_skills/exact_k-codebase-design/)                  |
| Boundary | design vocabulary only; SOP owns compatibility/scope; `k-code-quality` owns implementation style                      |
| Pivots   | resolves necessary in-scope diagnostic seam/design questions; `k-code-quality-tests` owns test mechanics once settled |

## `k-diagnosing-bugs`

| Field    | Value                                                                                                                                                        |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Use when | diagnosing a hard bug, failure, flake, or performance regression from source and observed failure evidence                                                   |
| Source   | [`exact_k-diagnosing-bugs`](../../../../home/exact_dot_agents/exact_skills/exact_k-diagnosing-bugs/)                                                         |
| Boundary | routes into SOP §3.5 plus SOP State-Machine Verification; not the runtime-truth chain for "is X set up right"                                                |
| Pivots   | necessary in-scope seam/design question → `k-codebase-design`; authorized regression cases → `k-code-quality-tests`; no automatic post-fix architecture pass |

Reuse existing failure evidence. Source investigation does not require a runnable reproduction first. New probes must resolve a material uncertainty; minimization and competing hypotheses are evidence-driven, not mandatory quotas. Production workers return artifacts without private QA; the root owns one integrated final verification.

Failure assessment identifies product, test, infrastructure, mixed, or unresolved causes. A green retry or a test-only patch does not establish a test-only defect; the original product behavior stays in the acceptance criteria.

## `k-prototype`

| Field    | Value                                                                                           |
| -------- | ----------------------------------------------------------------------------------------------- |
| Use when | building throwaway code to answer a design question (logic/state model, or what a UI should be) |
| Source   | [`exact_k-prototype`](../../../../home/exact_dot_agents/exact_skills/exact_k-prototype/)        |
| Boundary | explicit throwaway exception to artifact necessity; delete or absorb when done                  |
| Pivots   | closes `k-spec` empirical forks — the verdict returns to the packet's Context line              |

## `k-git`

| Field    | Value                                                                                                                                                                                                      |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | local git operations: status/diff/log, branching, committing, pushing, rebasing, conflicts                                                                                                                 |
| Source   | [`exact_k-git`](../../../../home/exact_dot_agents/exact_skills/exact_k-git/)                                                                                                                               |
| Boundary | no GitHub side effects; no worktree management; no commit without an explicit current-conversation request; configured remote URLs are never printed verbatim because URL userinfo may contain credentials |

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
| Use when | nontrivial diagnosis/implementation impact, review base context, or SCSI index selection                       |
| Source   | [`exact_k-semantic-code-search`](../../../../home/exact_dot_agents/exact_skills/exact_k-semantic-code-search/) |
| Boundary | not durable memory; use [Agent memory](../knowledge-base/index.md) for that                                    |

Discover and justify the index before querying it, then trace relevant symbols, callers, and consumers. Confirm snapshot findings against the exact local code. An unavailable or absent index, or an explicit opt-out, uses local `rg`/symbol evidence with a recorded reason; indexed `,sem` queries are not part of that fallback. Which repositories a SCSI server indexes is domain-overlay policy. Simple filename lookup and mechanical edits do not require semantic search.

## `k-sem` skill (`,sem` CLI)

| Field    | Value                                                                        |
| -------- | ---------------------------------------------------------------------------- |
| Use when | entity history across moves, per-entity blame, entity diff classification    |
| Source   | [`exact_k-sem`](../../../../home/exact_dot_agents/exact_skills/exact_k-sem/) |
| Tool     | `,sem` CLI                                                                   |

Index-free `diff`, `log`, and `blame` are the default surface: `diff --format json` proves a mechanical-only change (renames, moves, `structuralChange: false`), and `log <entity>` follows an entity across file moves where `git log -L` stops. Indexed queries (`impact`, `context`, `find`, `callers`, `refs`, `grep`, `entities`) build a multi-gigabyte per-worktree index and do not resolve `@kbn/*` package specifiers, so the skill forbids them unless the user explicitly asks.

## `k-weave`

| Field    | Value                                                                            |
| -------- | -------------------------------------------------------------------------------- |
| Use when | preparing merges, previewing/resolving conflicts at function/class granularity   |
| Source   | [`exact_k-weave`](../../../../home/exact_dot_agents/exact_skills/exact_k-weave/) |
| Tool     | `weave` CLI                                                                      |

Setup omits dedicated patterns for `.vue`, `.svelte`, `.erb`, and `.hs`. Compound names such as `.svelte.ts` can still match `*.ts`; preview and direct-driver calls can also attempt entity merging.

## `k-public-sources`

| Field    | Value                                                                                                                |
| -------- | -------------------------------------------------------------------------------------------------------------------- |
| Use when | inspecting public source, or synthesizing factual claims across multiple public sources                              |
| Source   | [`exact_k-public-sources`](../../../../home/exact_dot_agents/exact_skills/exact_k-public-sources/)                   |
| Boundary | explicit repo URLs stay source-first; multi-source synthesis carries primary evidence for one batched final judgment |

The multi-source branch collects and drafts the requested synthesis in one research assignment, retaining exact source identity, supporting passages and uncertainty. The final Verify stage judges material claims together using those artifacts. Unsupported claims are omitted or qualified; there are no per-claim verifiers, post-verification deepening loops or duplicate source fetches for independence. Final judgment preserves the required capability and reports reduced independence when applicable. Verified reusable insights enter the root's final `,ai-kb` learning batch, not leaf memory workflows.

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

## `k-instruction-boundaries`

| Field    | Value                                                                                                              |
| -------- | ------------------------------------------------------------------------------------------------------------------ |
| Use when | writing or refactoring AI-facing instructions that need hard prohibition boundaries                                |
| Source   | [`exact_k-instruction-boundaries`](../../../../home/exact_dot_agents/exact_skills/exact_k-instruction-boundaries/) |
| Routing  | user-invoked (`disable-model-invocation: true`); referenced by `k-writing-great-skills`                            |
| Boundary | hard prohibitions by default; affirmative wording only where it sharpens execution                                 |

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
