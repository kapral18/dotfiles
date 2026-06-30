---
sidebar_position: 3
title: Execution workflow
---

# Execution workflow

The SOP makes work resumable and testable before implementation starts.

## Intent loop

| Stage              | Output                                                                            |
| ------------------ | --------------------------------------------------------------------------------- |
| Investigate        | evidence that removes ambiguity without asking                                    |
| Intent spec        | target, action, success, constraints, scope bounds, side effects, example         |
| Fork inventory     | 2+ plausible interpretation or implementation forks that change the output        |
| Interview          | the most branch-eliminating fork-closing question, repeated until forks are empty |
| Plan               | response starts with a dedicated checklist and per-step verification              |
| Execute + validate | implementation plus acceptance checks                                             |
| Present results    | outcome, evidence, and remaining blockers                                         |

## Persistent spec

| Artifact             | Path                                           |
| -------------------- | ---------------------------------------------- |
| Active topic pointer | `/tmp/specs/<workspace>/_active_topic.txt`     |
| Topic spec           | `/tmp/specs/<workspace>/<topic>.txt`           |
| Worklog              | `/tmp/specs/<workspace>/<topic>.worklog.jsonl` |

Do not load specs broadly. Topic keys are broad, stable, kebab-case, and exactly one is active per prompt. `/tmp/specs` is ephemeral working memory used to rehydrate intent after pruning, not durable knowledge. Durable reusable learnings belong in [Agent memory](../knowledge-base/index.md).

## Verification loops

| Situation             | SOP response                                                                                                    |
| --------------------- | --------------------------------------------------------------------------------------------------------------- |
| bug fix               | reframe as a verifiable goal: write a test that reproduces the bug, then make it pass                           |
| refactor              | keep the existing behavior surface green                                                                        |
| parser/stateful logic | before final/merge-ready, build a `/tmp/state-machine-verification/...` harness with an independent model/table |
| repeated misses       | stop speculative edits and reset requirements                                                                   |

Test-first framing never expands scope beyond the request.
