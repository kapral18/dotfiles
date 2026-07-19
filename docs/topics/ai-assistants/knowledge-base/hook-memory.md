---
sidebar_position: 1
title: Hook memory
---

# Hook memory (`/tmp/specs`, `,agent-memory`)

Ephemeral session memory: inject context at start, record tool events to a crash-safe worklog, bind sessions to named topic buckets. Shared hooks deploy to `~/.agents/hooks/`; harness adapters differ — see [Runtime recall wiring](cross-agent-memory.md).

| Piece                                           | Role                                                  |
| ----------------------------------------------- | ----------------------------------------------------- |
| `session_context.py`                            | Session start: prefix, topic index/spec, worklog tail |
| `worklog_dispatcher.sh` → `worklog_recorder.py` | Post-tool: async JSONL append                         |
| `perturn_recall.py` + `correction_detector.py`  | Per-prompt: AI-KB recall + correction directive       |
| `/tmp/specs/<workspace>/`                       | Specs, worklogs, bindings (outside chezmoi/worktrees) |
| `,agent-memory`                                 | User/agent control plane                              |
| `spec_mirror.py`                                | Reboot survival → `~/.local/state/agent-specs/`       |

## Topic lifecycle

**Shared branches** (`main`, `master`, `dev`, `develop`, `trunk`) with no session binding: session start injects a `### Topic Buckets` index (newest first). Agent binds when exactly one bucket matches, creates when none match, asks when several match. Add `summary: <one-line>` to specs for scannability.

**Feature/topic worktrees** keep `current` continuity instead of the bucket index.

## `,agent-memory` commands

| Command                                     | Effect                                                                                                                               |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `status [--session-id <id>]`                | Selected topic; `--json` adds `session_key` for adapters                                                                             |
| `select <topic> --session-id <id>`          | Bind session; flush pre-bind `session-*` events into topic worklog; print clean-room context; never changes another session's bucket |
| `select <topic> --create --session-id <id>` | New bucket + bind                                                                                                                    |
| `note <kind> "<text>" [--ref <anchor>]`     | Structured worklog entry (capsule kinds + `question`/`decision`); surfaces in `,ai-kb harvest`                                       |
| `merge <src> <dest> [--dry-run]`            | Fold duplicate: flush queues, merge worklogs (200-line cap), rewrite bindings, delete source `.no_context`                           |
| `use <topic>`                               | Legacy workspace pointer (rejects `current`)                                                                                         |
| `wipe-current [--session-id <id>]`          | Delete spec/worklog/sentinel; default branch → latest `session-*`                                                                    |

## Harvest and corrections

`,ai-kb harvest --session-id <id>` mines the bound worklog for durable candidates (notes, failure→fix, recurring errors, repeated commands). Flushes pending queues first; exits nonzero if pending/error state remains. **Never writes capsules** — see [AI knowledge base](ai-kb.md#worklog-harvest).

`correction_detector.py` fires on narrow conduct patterns; `perturn_recall.py` injects a same-turn directive to `,agent-memory note anti_pattern` when genuine, and `,ai-kb remember` only after verification. Fail-open; no automatic writes.

## Clean session / clean-room

Force no injection: `AGENT_HOOK_CONTEXT=0`, or `_no_session_context` (workspace) or `<topic>.no_context`.

| Rule                                 | Why                                      |
| ------------------------------------ | ---------------------------------------- |
| Oversized specs omitted with pointer | No partial memory                        |
| Whole recent worklog entries only    | No half-events                           |
| Worklog trim during queue flush      | Bounded injection, no lost writes        |
| Per-session bindings                 | Parallel sessions join or isolate safely |
| Review topics clean-room by default  | Reduce re-review bias                    |

Review topics (`review*` name or PR in first `target:`): strip prior `verified facts`/`findings`/`verdict` and worklog tail before size check. Text over bound is omitted wholesale, never truncated.

`session_context.py` and `,agent-memory select` apply the same clean-room rules independently (mirrored code — change both together).

## Design contract

**Hooks observe and inject; they never re-prompt.** No hook on `stop`. Evidence anchoring and durable-learning capture are SOP habits (`~/AGENTS.md` §2–§4), not hook-enforced.

## Internals

**State layout** under `/tmp/specs/<workspace>/`:

```text
_active_topic.txt
.session-topic-<session-id>.txt
<topic>.txt / <topic>.worklog.jsonl
.recall-seen-<session-key>.json
.worklog-queue-v1/<session-key>/  .worklog-locks-v1/
```

| Contract          | Behavior                                                                                                                                                                                                                                          |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ordering          | Atomic sequence files and stable `worklog_id`/`session_key`/`worklog_seq` make replay idempotent; activity and target locks keep harvest complete and shared-topic logs ordered                                                                   |
| Bounds            | At most 256 pending events or 1 MiB per session; each worklog retains 200 complete JSONL records                                                                                                                                                  |
| Lifecycle         | The tool-call recorder flushes synchronously with no idle wait; the background flusher exits after 80 ms idle or two seconds total; seven-day cleanup covers drained queue/error state plus stale `session-*` worklogs and `.recall-seen-*` files |
| Failure behavior  | Tool calls fail open; startup warns about queue errors; harvest refuses pending/error state                                                                                                                                                       |
| Copilot subagents | `COPILOT_AGENT_SESSION_ID` routes writes to the parent session key; startup/read injection remains isolated                                                                                                                                       |
| Recall dedupe     | `.recall-seen-<session-key>.json` uses `conversation_id` → `session_id` → `generation_id` and is shared by BM25 warm-start and per-turn recall                                                                                                    |
| Reboot survival   | `spec_mirror.py` mirrors named topics and `_active_topic.txt` to `~/.local/state/agent-specs/`, restores only missing files, and excludes `current`/`session-*`; wipe/merge forget removals                                                       |

## Sources and verification

- [`executable_,agent-memory`](../../../../home/exact_bin/executable_,agent-memory), [`scripts/agent_memory.py`](../../../../scripts/agent_memory.py)
- [`exact_hooks/`](../../../../home/exact_dot_agents/exact_hooks/), [`scripts/spec_mirror.py`](../../../../scripts/spec_mirror.py)

```bash
python3 scripts/tests/test_agent_hooks.py
python3 -m unittest discover -s scripts -t scripts -k test_recall_worklog
python3 -m unittest discover -s scripts -t scripts -k test_agent_memory
,agent-memory status --session-id <id>
```
