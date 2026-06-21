---
sidebar_position: 3
title: Execution workflow
---

# Execution workflow

The SOP makes work resumable and testable before implementation starts.

## Reverse-interview loop

| Stage              | Output                                                                  |
| ------------------ | ----------------------------------------------------------------------- |
| Investigate        | evidence that removes ambiguity without asking                          |
| Intent spec        | target, action, success, constraints, scope, side effects, example      |
| Fork inventory     | remaining decision forks that change the output                         |
| Interview          | one fork-closing question at a time only when evidence cannot settle it |
| Plan               | checklist with per-step verification                                    |
| Execute + validate | implementation plus acceptance checks                                   |
| Present results    | outcome, evidence, and remaining blockers                               |

## Persistent spec

| Artifact             | Path                                           |
| -------------------- | ---------------------------------------------- |
| Active topic pointer | `/tmp/specs/<workspace>/_active_topic.txt`     |
| Topic spec           | `/tmp/specs/<workspace>/<topic>.txt`           |
| Worklog              | `/tmp/specs/<workspace>/<topic>.worklog.jsonl` |

`/tmp/specs` is ephemeral working memory, not durable knowledge. Durable reusable learnings belong in [Agent memory](../knowledge-base/index.md).

## Verification loops

| Situation             | SOP response                                           |
| --------------------- | ------------------------------------------------------ |
| bug fix               | reproduce or write a targeted check, then make it pass |
| refactor              | keep the existing behavior surface green               |
| parser/stateful logic | build a `/tmp/state-machine-verification/...` harness  |
| repeated misses       | stop speculative edits and reset requirements          |
