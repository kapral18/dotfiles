---
sidebar_position: 3
title: Execution workflow
---

# Execution workflow

The SOP makes work resumable and testable before implementation starts.

## Intent loop

| Stage              | Output                                                                                       |
| ------------------ | -------------------------------------------------------------------------------------------- |
| Investigate        | evidence that removes ambiguity without asking                                               |
| Intent spec        | target, action, success, constraints, scope bounds, side effects, example                    |
| Fork inventory     | 2+ plausible interpretation or implementation forks that change the output                   |
| Interview          | the most branch-eliminating fork-closing question, repeated until forks are empty            |
| Plan               | response starts with a dedicated checklist and per-step verification                         |
| Readiness gate     | before executing non-trivial work, confirm forks are empty and success criteria are testable |
| Execute + validate | implementation plus acceptance checks                                                        |
| Present results    | outcome, evidence, and remaining blockers                                                    |

When advising or reviewing a plan, prefer probing questions that surface assumptions and forks over prescribing a solution; withhold readiness until the plan's success criteria are testable.

## Persistent spec

| Artifact             | Path                                           |
| -------------------- | ---------------------------------------------- |
| Active topic pointer | `/tmp/specs/<workspace>/_active_topic.txt`     |
| Topic spec           | `/tmp/specs/<workspace>/<topic>.txt`           |
| Worklog              | `/tmp/specs/<workspace>/<topic>.worklog.jsonl` |

Do not load specs broadly. Topic keys are broad, stable, kebab-case, and exactly one is active per prompt. `/tmp/specs` is ephemeral working memory used to rehydrate intent after pruning, not durable knowledge. Durable reusable learnings belong in [Agent memory](../knowledge-base/index.md).

## Verification loops

| Situation                         | SOP response                                                                                                            |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| bug fix                           | reframe as a verifiable goal: write a test that reproduces the bug, then make it pass                                   |
| refactor                          | keep the existing behavior surface green                                                                                |
| parser/stateful logic             | before final/merge-ready, build a `/tmp/state-machine-verification/...` harness with an independent model/table         |
| rationale claims input irrelevant | perturb exactly that input and confirm the decision is stable; a flip means the stated rationale is not the real driver |
| repeated misses                   | stop speculative edits and reset requirements                                                                           |

Test-first framing never expands scope beyond the request.

## Harness search interop

Harness-native search/listing tools are the interop layer for broad code search. Prefer native Grep/Glob/search tools for first-pass broad searches; use shell `rg` only after narrowing by path, glob, or exact symbol. Never run bare repo-root `rg <pattern>` in a large repository.
