---
sidebar_position: 2
title: AI knowledge base
---

# AI knowledge base (`,ai-kb`)

Durable cross-session memory: markdown capsules, SQLite mirror, subprocess-isolated embeddings. CLI runs from `~/lib/,ai-kb/` (rendered from repo modules).

| Piece    | Path                                                                                                                                                |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| CLI      | `~/bin/,ai-kb`                                                                                                                                      |
| Capsules | `~/.local/share/ai-kb/capsules/<id>.md`                                                                                                             |
| SQLite   | `~/.local/share/ai-kb/kb.sqlite3`                                                                                                                   |
| Source   | [`scripts/ai_kb.py`](../../../../scripts/ai_kb.py), [`home/exact_lib/exact_,ai-kb/`](../../../../home/exact_lib/exact_,ai-kb/readonly_main.py.tmpl) |

## Commands

```bash
,ai-kb search "<actual task query>" --limit 5 --json
,ai-kb get <id>
,ai-kb remember --title "..." --body "..." --kind gotcha --scope project --workspace "$(pwd)" \
                --source "path:line" --confidence 0.9 --domain chezmoi
,ai-kb ingest ./docs
,ai-kb reembed
,ai-kb curate
,ai-kb harvest --session-id <id>
,ai-kb harvest --worklog PATH --json
,ai-kb doctor
```

Search also supports kind, scope, workspace, domain, and mode filters. `curate` runs dedupe, decay, and contradiction detection together; `--no-*` flags skip individual lanes. Metadata drives retrieval and curation; the complete write contract lives in `~/.agents/skills/k-ai-kb/SKILL.md`. Markdown backticks in a double-quoted `--body` trigger shell substitution, so use single quotes or escape them.

**Palantír:** role panes use explicit `,ai-kb search`/`remember`; close-out durable findings → `remember`; task notes stay in `/tmp/specs`; repo conventions → target `AGENTS.md`.

## Capsule model

Sidecar markdown is canonical for content/identity; SQLite holds curation/runtime state.

| Field                               | Purpose                                                                               |
| ----------------------------------- | ------------------------------------------------------------------------------------- |
| `kind`                              | `fact`/`gotcha`/`pattern`/`anti_pattern`/`recipe`/`principle`/`doc`                   |
| `scope`                             | `workspace`/`project`/`domain`/`universal`                                            |
| `tags`/`domain_tags`/`refs`         | Retrieval taxonomy and provenance links                                               |
| `confidence`/`verified_by`          | 0–1 + verifier role                                                                   |
| `supersedes`/`superseded_by`        | Dedupe links; superseded excluded from search                                         |
| `decay_score`                       | Incremented by the `curate` decay pass; cleared on retrieval (14-day shield)          |
| `embedding`/`embedding_model`/`dim` | Default `BAAI/bge-small-en-v1.5`, 384d via [`embed.py`](../../../../scripts/embed.py) |

Write-time dedup refuses a case-insensitive title collision or same-kind cosine ≥ 0.95 unless the caller explicitly supersedes the old capsule or confirms a false positive with `--force`. Degraded metadata warns rather than silently storing. Schema drift rebuilds from sidecars and fails before mutation when a sidecar is malformed.

## Retrieval

Hybrid search combines FTS5/BM25 and cosine (`sqlite-vec` via [`vec_runner.py`](../../../../scripts/vec_runner.py)), then applies RRF and MMR. Workspace matches receive a soft boost and superseded capsules stay hidden. Without embeddings, `bm25` remains available and `hybrid` returns its lexical lane; a vector-runner failure surfaces instead of silently changing hybrid semantics. Escape hatches: `AI_KB_DISABLE_EMBED=1` and `AI_KB_DISABLE_VEC=1`.

## Embedding lanes

| Lane     | When                       | Path                                                                              |
| -------- | -------------------------- | --------------------------------------------------------------------------------- |
| One-shot | CLI, `remember`, `reembed` | `embed_runner.py` (PEP 723 uv)                                                    |
| Resident | Per-turn recall only       | `embed_worker.py` + `embed_client.py`; generation-specific socket; 300s idle exit |

Per-turn callers set `AI_EMBED_CONNECT_ONLY=1` and never spawn or replace the worker. Session start may run a bounded `ensure` when depth is not `fast`. Runtime state and sockets are user-only; bounded socket payloads carry prompt text, and the worker never logs or echoes it. See [Runtime recall wiring](cross-agent-memory.md) for depth budgets and harness warm-up.

## Worklog harvest

Four deterministic detectors on `/tmp/specs/.../<topic>.worklog.jsonl` ([hook memory](hook-memory.md)):

| Detector           | Signal                                | Kind        |
| ------------------ | ------------------------------------- | ----------- |
| `structured_note`  | `,agent-memory note` (not `question`) | note's kind |
| `failure_to_fix`   | fail then clean same command          | `gotcha`    |
| `recurring_error`  | repeated error signature              | `gotcha`    |
| `repeated_command` | repeated clean command                | `recipe`    |

Harvest is read-only and never writes capsules. It flushes the queue first, exits nonzero on pending/error, and suppresses candidates already in the KB (BM25 + token overlap). **`decision` → `fact` candidate.** The agent verifies candidates and runs emitted `remember` lines.

Shell-derived detectors are naturally failure-biased. `structured_note` is the deliberate capture path for decisions, ideas, and constraints that produce no failing command.

## Sources and verification

- [`executable_,ai-kb`](../../../../home/exact_bin/executable_,ai-kb), [`scripts/ai_kb.py`](../../../../scripts/ai_kb.py)
- [`embed*.py`](../../../../scripts/), [`vec_runner.py`](../../../../scripts/vec_runner.py), [`worklog_queue.py`](../../../../scripts/worklog_queue.py)

```bash
python3 scripts/test_embed.py
python3 -m unittest discover -s scripts -t scripts -k test_agent_memory
,ai-kb doctor
```
