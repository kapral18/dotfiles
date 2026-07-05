---
sidebar_position: 2
title: AI knowledge base
---

# AI knowledge base (`,ai-kb`)

`,ai-kb` is the durable memory layer Ralph reads from and writes to.

| Piece          | Path                                                                               |
| -------------- | ---------------------------------------------------------------------------------- |
| CLI            | [`home/exact_bin/executable_,ai-kb`](../../../../home/exact_bin/executable_,ai-kb) |
| Implementation | [`scripts/ai_kb.py`](../../../../scripts/ai_kb.py)                                 |
| Capsules       | `~/.local/share/ai-kb/capsules/<id>.md`                                            |
| SQLite mirror  | `~/.local/share/ai-kb/kb.sqlite3`                                                  |

Capsule markdown is canonical. The SQLite mirror is rebuilt when schema changes: if `CAPSULE_COLUMNS` drifts, `init()` drops `capsules` / `capsule_fts` / `kb_meta` and recreates them. Markdown sidecars survive, so `,ai-kb ingest` can rehydrate.

Capsule shape:

| Field                                   | Purpose                                                                                                |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `kind`                                  | `fact` / `gotcha` / `pattern` / `anti_pattern` / `recipe` / `principle` / `doc`                        |
| `scope`                                 | `workspace` / `project` / `domain` / `universal` (controls reuse across runs and projects)             |
| `tags` / `domain_tags`                  | Free-form (TUI badges) and structured taxonomy (e.g. `auth`, `tmux`, `rust`)                           |
| `confidence` / `verified_by`            | Float 0-1 + role/run that verified it; reflectors and reviewers raise these                            |
| `supersedes` / `superseded_by`          | Bidirectional links built by `,ai-kb curate dedupe`; superseded capsules drop out of search            |
| `refs`                                  | Run / iteration / role / file refs so a hit can jump back to its origin                                |
| `embedding` / `embedding_model` / `dim` | Packed `float32` vector + provenance; populated via [`scripts/embed.py`](../../../../scripts/embed.py) |
| `decay_score`                           | Incremented by `,ai-kb curate decay` for capsules nobody retrieves; surfaces stale memory              |

Retrieval is hybrid by default:

| Stage           | Mechanism                                                                  |
| --------------- | -------------------------------------------------------------------------- |
| Lexical         | FTS5/BM25                                                                  |
| Dense           | Cosine over capsule embeddings, accelerated by `sqlite-vec`'s `vec0` table |
| Fusion          | Reciprocal Rank Fusion                                                     |
| Diversification | Maximal Marginal Relevance                                                 |
| Filters         | `kind`, `scope`, `workspace_path`, `domain_tags`                           |

Workspace matches get a soft RRF boost, so project capsules outrank global ones in the active workspace. Superseded capsules are excluded by default. See `KnowledgeBase.search` in [`scripts/ai_kb.py`](../../../../scripts/ai_kb.py).

Embeddings are isolated out of the orchestrator process:

| Component                                                        | Role                                                    |
| ---------------------------------------------------------------- | ------------------------------------------------------- |
| [`scripts/embed.py`](../../../../scripts/embed.py)               | stdlib wrapper that shells out via JSON stdin/stdout    |
| [`scripts/embed_runner.py`](../../../../scripts/embed_runner.py) | PEP 723 `uv run --script` runner that loads `fastembed` |
| Model                                                            | `BAAI/bge-small-en-v1.5`, 384 dimensions                |
| Escape hatch                                                     | `RALPH_KB_DISABLE_EMBED=1`                              |

When embeddings are disabled, lexical retrieval still works.

Vector search and curation pairs use the same subprocess-isolation pattern:

| Component                                                    | Role                                                         |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| [`scripts/vec_runner.py`](../../../../scripts/vec_runner.py) | PEP 723 `uv run --script` runner that loads `sqlite-vec`     |
| `vec_index`                                                  | Virtual table lazily created from `capsules.embedding` BLOBs |
| Sync model                                                   | Delta-synced on every call                                   |
| Escape hatch                                                 | `RALPH_KB_DISABLE_VEC=1`                                     |

The orchestrator process never loads SQLite extensions, which matters on Apple's stock Python. Errors hard-fail with `RuntimeError` rather than silently degrading to BM25-only.

Curation also goes through `vec_runner`: KNN shortlist plus per-pair cosine replaces the old O(N²) Python loop for dedupe and contradiction scans.

Memory flow during a Ralph run:

1. Each role's prompt builder calls `KnowledgeBase.search(...)` filtered to that role's preferred kinds. Planner gets the broadest slice (no kind filter — anything prior may influence planning, with workspace bias surfacing project-local capsules first). Executor: `fact / recipe / gotcha / anti_pattern / pattern`. Reviewer: `gotcha / anti_pattern`. Re_reviewer: `gotcha / anti_pattern / principle`. Hits are injected into a `## RECENT LEARNINGS` block in the role prompt and a compressed copy is persisted to `manifest.json::roles[*].retrieval_log` for TUI replay.
2. Roles can also call the KB on demand from inside their pane (`,ai-kb search "<q>" --kind gotcha,anti_pattern --json`) — see the `Tool: on-demand KB search` section in each prompt.
3. Roles emit `LEARNING:` lines (free-form `gotcha`/`principle`/`fact`/`decision`); `,ralph` parses these in [`RalphRunner.capture_learnings`](../../../../scripts/ralph.py) and stores them with `kind` inferred from role and `scope=project` when a workspace is set.
4. After a passing run the dedicated `reflector` role distills the run into a small JSON list of structured capsules (see [`reflector.md`](../../../../home/dot_config/ralph/prompts/reflector.md)) which are validated and persisted, giving the next run high-signal retrieval material.

CLI surface:

```bash
# Metadata is not optional decoration — every field drives retrieval/curation.
# Full write contract (field selection, --source/--confidence discipline, body
# structure, supersede limitation): ~/.agents/skills/ai-kb/SKILL.md.
,ai-kb remember --title "chezmoi: generated state must stay out of git" \
                --body "Keep generated state out of git; verified in scripts/foo.py:42." \
                --kind principle --scope project --workspace "$(pwd)" \
                --source "scripts/foo.py:42" --confidence 0.9 --domain chezmoi --tags lint
,ai-kb search "tmux capture-pane reuse"           # hybrid (lexical + vector)
,ai-kb search --kind gotcha --scope project --json
,ai-kb remember --title "..." --body "..." --supersedes <old-id> --confidence 0.9
                                                   # retire a stale capsule (links both ways; --supersedes is validated)
,ai-kb get <capsule-id>                            # full body + metadata
,ai-kb ingest ./AGENTS.md ./docs                   # chunk markdown into kind=doc capsules; idempotent on sha256
,ai-kb reembed                                     # rebuild missing/stale embeddings
,ai-kb curate dedupe                               # mark near-duplicates as superseded
,ai-kb curate decay                                # bump decay_score on dormant capsules
,ai-kb curate contradiction                       # flag suspicious gotcha vs fact pairs
,ai-kb harvest                                     # surface durable-memory candidates from the active topic's worklog (read-only)
,ai-kb harvest --worklog PATH --json               # explicit worklog + machine-readable candidates
,ai-kb doctor                                      # capsule count, FTS sanity, embedding coverage
```

Shell quoting still applies when an agent writes prose through `,ai-kb remember`. Markdown backticks inside a double-quoted `--body "..."` are command substitution, not formatting.

Use one of:

- single quotes for prose.
- escaped backticks.
- another argv-safe pattern when text also contains single quotes.

## Worklog harvest

`,ai-kb harvest` mines a topic worklog written by the agent hooks (`/tmp/specs/<workspace-without-leading-slash>/<topic>.worklog.jsonl`, see [hook memory](hook-memory.md)) and surfaces durable-memory candidates through three deterministic, stdlib-only detectors:

| Detector           | Signal                                                                      | Suggested kind |
| ------------------ | --------------------------------------------------------------------------- | -------------- |
| `failure_to_fix`   | A failing command later followed by a clean run of the same program         | `gotcha`       |
| `recurring_error`  | The same digit-normalized error signature seen `--min-repeats`+ times       | `gotcha`       |
| `repeated_command` | The same clean command run `--min-repeats`+ times (noise programs excluded) | `recipe`       |

For each candidate it prints the evidence lines and a ready-to-edit `,ai-kb remember` line. Candidates already covered by a capsule are suppressed via a BM25 lookup plus a token-overlap match, so harvest does not re-suggest what is already remembered. It defaults to the active topic (`/tmp/specs/<ws>/_active_topic.txt`, else `current`); `--worklog PATH` overrides the path and `--json` emits the full candidate set (including suppressed ones flagged `known`).

`harvest` **never writes capsules** — you verify each candidate and run the emitted `remember` line yourself. It is a manual, on-demand aid with no hook, no `additionalContext` injection, and no auto-submit, so it adds no always-on token cost and cannot re-trigger a conversation. Persistence stays agent-driven per the [ai-kb skill](../skills/index.md) write contract.

The Ralph TUI exposes the KB with a `K` keybinding: a modal launches `,ai-kb search ... --json` over stdin/stdout; navigation is `↑/↓`, `enter` to dispatch a search, `esc`/`q` to close. The status bar shows total capsule count (`KB:N`).
