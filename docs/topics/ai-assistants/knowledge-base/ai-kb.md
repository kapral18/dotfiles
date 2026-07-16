---
sidebar_position: 2
title: AI knowledge base
---

# AI knowledge base (`,ai-kb`)

`,ai-kb` is the durable memory layer shared by governed agents, manual searches, and Palantír close-out routing. It stores authored capsules as markdown sidecars, mirrors them into SQLite for search and curation, and keeps embeddings isolated from the caller process. This page covers the capsule model, CLI use, retrieval pipeline, embedding lanes, and worklog harvest.

The moving parts:

| Piece          | Path / role                                                                                                       |
| -------------- | ----------------------------------------------------------------------------------------------------------------- |
| CLI            | [`home/exact_bin/executable_,ai-kb`](../../../../home/exact_bin/executable_,ai-kb)                                |
| Deployed core  | [`home/exact_lib/exact_,ai-kb/`](../../../../home/exact_lib/exact_,ai-kb/readonly_main.py.tmpl) → `~/lib/,ai-kb/` |
| Source modules | [`scripts/ai_kb.py`](../../../../scripts/ai_kb.py) and the colocated retrieval/embedding modules                  |
| Capsules       | `~/.local/share/ai-kb/capsules/<id>.md`                                                                           |
| SQLite mirror  | `~/.local/share/ai-kb/kb.sqlite3`                                                                                 |

## Using it

Use `,ai-kb search` for durable recall, `,ai-kb get` for a full capsule, and `,ai-kb remember` only for verified reusable facts, gotchas, recipes, patterns, principles, and docs. Metadata is not optional decoration: kind, scope, source, confidence, domains, and tags affect retrieval and curation.

```bash
# Metadata is not optional decoration — every field drives retrieval/curation.
# Full write contract (field selection, --source/--confidence discipline, body
# structure, supersede limitation): ~/.agents/skills/k-ai-kb/SKILL.md.
,ai-kb remember --title "chezmoi: generated state must stay out of git" \
                --body "Keep generated state out of git; verified in scripts/foo.py:42." \
                --kind principle --scope project --workspace "$(pwd)" \
                --source "scripts/foo.py:42" --confidence 0.9 --domain chezmoi --tags lint
,ai-kb search "tmux capture-pane reuse"           # hybrid (lexical + vector)
,ai-kb search --kind gotcha --scope project --json
,ai-kb search --workspace "$(pwd)" --workspace-gate "query"
                                                   # hard-filter to workspace-local or domain/universal capsules
                                                   # (the gate automatic hook/extension recall relies on)
,ai-kb remember --title "..." --body "..." --supersedes <old-id> --confidence 0.9
                                                   # retire a stale capsule (links both ways; --supersedes is validated)
,ai-kb get <capsule-id>                            # full body + metadata
,ai-kb ingest ./AGENTS.md ./docs                   # chunk markdown into kind=doc capsules; idempotent on sha256
,ai-kb reembed                                     # rebuild missing/stale embeddings
,ai-kb curate dedupe                               # mark near-duplicates as superseded
,ai-kb curate decay                                # bump decay_score on dormant capsules (skips any retrieved in the last 14 days)
,ai-kb curate contradiction                       # flag suspicious gotcha vs fact pairs
,ai-kb harvest --session-id <id>                   # surface candidates from this session's bound topic (read-only)
,ai-kb harvest --worklog PATH --json               # explicit worklog + machine-readable candidates
,ai-kb doctor                                      # capsule count, FTS sanity, embedding coverage
```

Shell quoting still applies when an agent writes prose through `,ai-kb remember`. Markdown backticks inside a double-quoted `--body "..."` are command substitution, not formatting.

Use one of:

- single quotes for prose.
- escaped backticks.
- another argv-safe pattern when text also contains single quotes.

During a Palantír legion:

1. Coordinator and role panes are ordinary governed harness sessions, so they can use the `k-ai-kb` skill for explicit searches before non-trivial work.
2. Role panes can call the KB on demand from inside their pane, for example `,ai-kb search "<q>" --kind gotcha --json`.
3. On close, durable reusable findings route to `,ai-kb remember` with deliberate metadata; task-scoped notes stay in `/tmp/specs`; repo-intrinsic conventions belong in the target repo's `AGENTS.md` through the legion worktree.

The Palantír dashboard shows legion state; durable-memory search and writes remain explicit `,ai-kb` CLI or skill actions.

## Capsule model

Capsule markdown is canonical for authored capsule content and identity metadata. Mutable curation/runtime state lives in SQLite: `superseded_by`, `decay_score`, `retrieved_at`/`retrieval_count`, embeddings, and `updated_at`.

| Field                                   | Purpose                                                                                                        |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `kind`                                  | `fact` / `gotcha` / `pattern` / `anti_pattern` / `recipe` / `principle` / `doc`                                |
| `scope`                                 | `workspace` / `project` / `domain` / `universal` (controls reuse across runs and projects)                     |
| `tags` / `domain_tags`                  | Free-form (TUI badges) and structured taxonomy (e.g. `auth`, `tmux`, `rust`)                                   |
| `confidence` / `verified_by`            | Float 0-1 + role/run that verified it; reflectors and reviewers raise these                                    |
| `supersedes` / `superseded_by`          | Bidirectional links built by `,ai-kb curate dedupe`; superseded capsules drop out of search                    |
| `refs`                                  | Run / iteration / role / file refs so a hit can jump back to its origin                                        |
| `embedding` / `embedding_model` / `dim` | Packed `float32` vector + provenance; populated via [`scripts/embed.py`](../../../../scripts/embed.py)         |
| `decay_score`                           | Incremented by `,ai-kb curate decay` for dormant capsules; any retrieval clears it, so live memory never sinks |
| `retrieved_at` / `retrieval_count`      | SQLite-only usage state stamped by every `search` hit; shields a capsule from decay for 14 days                |

Write-time dedup refuses an exact case-insensitive title collision with a live capsule, and also refuses a same-kind embedding cosine ≥ 0.95, naming the existing capsule id. Pass `--supersedes <that-id>` to retire it, or `--force` for a genuine false positive. Degraded metadata, including out-of-range `--confidence`, defaulted `--source`, or missing `--domain`, prints a warning instead of being silently stored.

When `CAPSULE_COLUMNS` drifts, `init()` transactionally rebuilds `capsules` from sidecars and overlays recoverable SQL-only state from the pre-drop table. When only `capsule_fts` / `kb_meta` drift, it rebuilds those derived tables from the current `capsules` rows. If a sidecar is malformed, rebuild fails closed before mutation instead of silently returning an empty KB.

## Retrieval pipeline

Retrieval is hybrid by default:

| Stage           | Mechanism                                                                  |
| --------------- | -------------------------------------------------------------------------- |
| Lexical         | FTS5/BM25                                                                  |
| Dense           | Cosine over capsule embeddings, accelerated by `sqlite-vec`'s `vec0` table |
| Fusion          | Reciprocal Rank Fusion                                                     |
| Diversification | Maximal Marginal Relevance                                                 |
| Filters         | `kind`, `scope`, `workspace_path`, `domain_tags`                           |

Workspace matches get a soft RRF boost, so project capsules outrank global ones in the active workspace. Superseded capsules are excluded by default. See `KnowledgeBase.search` in [`scripts/ai_kb.py`](../../../../scripts/ai_kb.py).

When embeddings are disabled or unavailable outside the cosine-gated per-turn lane, lexical retrieval still works.

## Embedding and vector lanes

Embeddings are isolated out of the caller process, with two deliberately separate lanes:

| Component                                                          | Role                                                                                                                                     |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| [`scripts/embed.py`](../../../../scripts/embed.py)                 | stdlib dispatch layer; defaults to the one-shot runner and uses resident connect-only mode only when `AI_EMBED_CONNECT_ONLY=1`           |
| [`scripts/embed_runner.py`](../../../../scripts/embed_runner.py)   | PEP 723 `uv run --script` runner that loads `fastembed` for ordinary CLI, manual search, `remember`, and `reembed` operations            |
| [`scripts/embed_client.py`](../../../../scripts/embed_client.py)   | generation-specific Unix-socket client; session-start adapters may call bounded `ensure`, while per-turn callers always use connect-only |
| [`scripts/embed_worker.py`](../../../../scripts/embed_worker.py)   | resident PEP 723 FastEmbed worker used only by automatic per-turn recall                                                                 |
| [`scripts/worklog_queue.py`](../../../../scripts/worklog_queue.py) | bounded, crash-safe worklog queue flushed before harvest                                                                                 |
| Model                                                              | `BAAI/bge-small-en-v1.5`, 384 dimensions                                                                                                 |
| Escape hatch                                                       | `AI_KB_DISABLE_EMBED=1`                                                                                                                  |

The resident identity hashes the protocol version, complete worker source, model, and expected dimension. Each generation gets its own socket, so a new implementation cannot replace or send requests to an older process. Warm-up resolves the configured `AI_EMBED_MODEL` dimension from FastEmbed metadata; connect-only callers discover and validate that ready generation without spawning.

The runtime root is user-owned `0700`, sockets and start locks are `0600`, startup markers are atomically published and bound to the expected worker command, and resident-worker request sizes and deadlines are bounded. The worker receives text only in the socket payload and never logs or echoes it.

One resident `BAAI/bge-small-en-v1.5` worker measured about 320 MiB RSS; two coexisting deployment generations measured about 625 MiB total. The worker exits after 300 inactive seconds and removes only the socket inode it created, bounding that temporary overlap without cross-generation eviction.

Claude, Gemini, Codex, OpenCode, Copilot, and Pi request a bounded, fail-open resident warm-up when `AI_AGENT_DEPTH` is `balanced` or `deep`; `fast` suppresses warm-up because it has no per-turn retrieval. Cursor does not start the worker because it has no per-turn retrieval adapter.

Every per-turn search sets `AI_EMBED_CONNECT_ONLY=1`: it never starts, restarts, or replaces a worker, and an unavailable resident simply suppresses that recall block without interrupting the user request. Default/manual CLI use plus `remember` and `reembed` work stay on the existing one-shot runner. The exact depth budgets and provenance are documented in [Cross-agent memory](cross-agent-memory.md).

Vector search and curation pairs use the same subprocess-isolation pattern:

| Component                                                    | Role                                                         |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| [`scripts/vec_runner.py`](../../../../scripts/vec_runner.py) | PEP 723 `uv run --script` runner that loads `sqlite-vec`     |
| `vec_index`                                                  | Virtual table lazily created from `capsules.embedding` BLOBs |
| Sync model                                                   | Delta-synced on every call                                   |
| Escape hatch                                                 | `AI_KB_DISABLE_VEC=1`                                        |

The orchestrator process never loads SQLite extensions, which matters on Apple's stock Python. Errors hard-fail with `RuntimeError` rather than silently degrading to BM25-only.

Curation also goes through `vec_runner`: KNN shortlist plus per-pair cosine is used for dedupe and contradiction scans.

## Internals (for maintainers)

The public command runs directly from `~/lib/,ai-kb/main.py` and does not discover or import the chezmoi checkout at runtime. The deployed library is rendered from the repository modules, so the CLI, hooks, and resident worker share one implementation while remaining usable outside the source checkout.

## Worklog harvest

`,ai-kb harvest` mines a topic worklog written by the agent hooks (`/tmp/specs/<workspace-without-leading-slash>/<topic>.worklog.jsonl`, see [hook memory](hook-memory.md)) and surfaces durable-memory candidates through four deterministic, stdlib-only detectors:

| Detector           | Signal                                                                                           | Suggested kind                                                  |
| ------------------ | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| `structured_note`  | A deliberate `,agent-memory note` event (one occurrence suffices; `question` notes are excluded) | The note's own kind — notes share the capsule taxonomy verbatim |
| `failure_to_fix`   | A failing command later followed by a clean run of the same program                              | `gotcha`                                                        |
| `recurring_error`  | The same digit-normalized error signature seen `--min-repeats`+ times                            | `gotcha`                                                        |
| `repeated_command` | The same clean command run `--min-repeats`+ times (noise programs excluded)                      | `recipe`                                                        |

The command lenses can only see shell activity, so they are structurally biased toward failures. `structured_note` is the deliberate capture surface for the decisions, ideas, and constraints that leave no failing command behind. Note kinds are the capsule kinds (minus `doc`) plus task-scoped `question`, so harvested candidates keep their kind verbatim.

Before reading candidates, harvest flushes the bounded session-keyed worklog queue for the target spec directory. It exits nonzero when a queue record remains pending or an active error ledger exists, so asynchronous bookkeeping cannot be mistaken for a complete harvest.

For each candidate it prints the evidence lines and a ready-to-edit `,ai-kb remember` line. Candidates already covered by a capsule are suppressed via a BM25 lookup plus a token-overlap match, so harvest does not re-suggest what is already remembered.

Pass `--session-id <id>` to resolve the same `.session-topic-<id>.txt` binding used by hooks. Without it, `agent_memory.py` applies its normal explicit-pointer/branch/default fallback. An explicit `--topic` overrides the session binding, `--worklog PATH` overrides topic resolution entirely, and `--json` emits the full candidate set, including suppressed ones flagged `known`.

`harvest` **never writes capsules** — you verify each candidate and run the emitted `remember` line yourself. It is a manual, on-demand aid with no hook, no `additionalContext` injection, and no auto-submit, so it adds no always-on token cost and cannot re-trigger a conversation. Persistence stays agent-driven per the [ai-kb skill](../skills/index.md) write contract.

## Sources and verification

- [`home/exact_bin/executable_,ai-kb`](../../../../home/exact_bin/executable_,ai-kb)
- [`home/exact_lib/exact_,ai-kb/`](../../../../home/exact_lib/exact_,ai-kb/readonly_main.py.tmpl)
- [`scripts/ai_kb.py`](../../../../scripts/ai_kb.py)
- [`scripts/embed.py`](../../../../scripts/embed.py)
- [`scripts/embed_runner.py`](../../../../scripts/embed_runner.py)
- [`scripts/embed_client.py`](../../../../scripts/embed_client.py)
- [`scripts/embed_worker.py`](../../../../scripts/embed_worker.py)
- [`scripts/vec_runner.py`](../../../../scripts/vec_runner.py)
- [`scripts/worklog_queue.py`](../../../../scripts/worklog_queue.py)
