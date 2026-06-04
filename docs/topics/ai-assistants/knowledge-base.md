---
sidebar_position: 3
---

# Agent Memory

Two distinct memory layers feed the assistants:

- **Hook memory** (`/tmp/specs`, managed by `,agent-memory`) — short-lived, per-workspace topic spec + worklog + evidence ledger, written by the Cursor CLI hooks during a session.
- **AI knowledge base** (`,ai-kb`, under `~/.local/share/ai-kb/`) — durable structured capsules shared across agents. [Ralph](ralph.md) reads/writes them mechanically across runs; interactive agents (cursor-cli, pi) read/write them on demand via the `ai-kb` skill (see [Cross-agent memory](#cross-agent-memory-ai-kb-skill)).

## Hook memory (`/tmp/specs`, `,agent-memory`)

Cursor CLI is the primary interactive assistant harness. User-level hooks are installed from [`home/dot_cursor/hooks.json`](../../../home/dot_cursor/hooks.json) to `~/.cursor/hooks.json` and call shared scripts deployed from [`home/exact_dot_agents/exact_hooks/`](../../../home/exact_dot_agents/exact_hooks/) to `~/.agents/hooks/`.

The hook layer is Cursor-native first:

| Event                                                                       | Script                | Purpose                                                                                                                                                                                                                                                   |
| --------------------------------------------------------------------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sessionStart`                                                              | `session_context.py`  | Inject the verification-discipline prefix (`prefix.txt`); inject the active `/tmp/specs` topic spec plus recent worklog tail when present; nudge to set a named topic on shared-branch sessions; remind to recall/remember durable knowledge via `,ai-kb` |
| `afterShellExecution`, `postToolUse`, `postToolUseFailure`, `afterFileEdit` | `worklog_recorder.py` | Append compact per-topic JSONL worklog entries                                                                                                                                                                                                            |

No hook runs on `stop`. Hooks observe and inject context; they do not re-prompt the agent. Two disciplines that earlier lived in `stop` hooks now live in the SOP, enforced by instruction rather than by an auto-submitted follow-up message:

- **Evidence anchoring** — a factual/runtime claim must carry a hard source anchor (file path, command/probe output, test result, or freshly fetched docs URL) or be explicitly demoted to `Unknown` with a reason (`~/CLAUDE.md` §2.1 External Truth / §2.3 Completion). The earlier `evidence_anchor.py` hook re-prompted per turn and was removed as noise.
- **Durable-learning capture** — as the last step of any substantive turn, the agent self-vets whether it produced a durable, verified, reusable insight and, if so, persists it inline with `,ai-kb remember` (`~/CLAUDE.md` §4.3, mirrored in `~/AGENTS.md` / `~/.gemini/GEMINI.md`). This replaces the earlier `learning_reminder.py` `stop` hook, whose auto-submitted "persist learnings" prompt was both intrusive and capped at once per conversation. The SOP habit has no per-session cap and never injects a fake user turn.

At session start, all three interactive harnesses also inject the verification-discipline prefix from [`prefix.txt`](../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt) — the same text the [tmux agent-prompt wrap](tool-configs.md) pastes manually — so the grounding discipline is in context from the first turn without pasting it. The file is the single source of truth, read at runtime: `session_context.py` injects it at `sessionStart` for Cursor CLI and Claude, and pi's `ai-kb-recall.ts` injects it once at the first `before_agent_start`. (cursor-agent has no per-prompt context-injection hook — `beforeSubmitPrompt` is allow/block only — so this is once-per-session there; pi could inject it per turn but does not, to avoid repeating the fixed block.)

Runtime state is intentionally outside chezmoi and outside worktrees:

```text
/tmp/specs/<workspace-path-without-leading-slash>/_active_topic.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.worklog.jsonl
```

This memory layer is bounded without injecting partial memory. Oversized topic specs are omitted with a pointer to the full file instead of being sliced into the prompt, and only whole recent worklog entries are included. Worklog JSONL files are trimmed on write. Shared default-branch workspaces (`main`, `master`, `dev`, `develop`, `trunk`) use session-scoped topics when no explicit non-`current` topic is active, so unrelated sessions do not inherit the generic `current` memory. Feature/topic worktrees keep `current` continuity by default. On a shared-branch session with no explicit topic (a `session-*` fallback), `session_context.py` injects a short nudge to set a named topic — this is how continuity is recovered on `main` without cross-contaminating other work on the same branch. Review topics also run in clean-room mode by default: startup context keeps neutral metadata but omits prior verified-facts, findings, verdicts, inline comments, and worklog tails so re-reviews are less biased by prior conclusions. To force a fully clean session, start the agent with `AGENT_HOOK_CONTEXT=0` or place a `_no_session_context` / `<topic>.no_context` sentinel under the workspace's `/tmp/specs/...` directory and remove it when context injection should resume.

The user-facing dead switch is `,agent-memory` ([`home/exact_bin/executable_,agent-memory`](../../../home/exact_bin/executable_,agent-memory) + [`scripts/agent_memory.py`](../../../scripts/agent_memory.py)): `,agent-memory status` shows the selected workspace topic; `,agent-memory use <topic>` pins a named active topic (writes `_active_topic.txt` and seeds `<topic>.txt`, rejecting the generic `current`), giving shared-branch sessions distinct, contamination-free continuity; and `,agent-memory wipe-current` deletes that topic's spec, worklog, and no-context sentinel without touching other topics. On default branches without an explicit active topic, `wipe-current` targets the latest `session-*` topic. Fish completions are installed from `home/dot_config/fish/completions/readonly_,agent-memory.fish` for the subcommands, shared options, wipe flags, and existing topic names.

Claude Code mirrors only the proven shared subset through [`home/dot_claude/settings.personal.json`](../../../home/dot_claude/settings.personal.json) and [`home/dot_claude/settings.work.json`](../../../home/dot_claude/settings.work.json): session context and tool worklog recording. The local llama.cpp settings file is intentionally excluded. Pi has no verified hook lifecycle, so it remains static-prompt only.

Verification:

```bash
python3 scripts/tests/test_agent_hooks.py
chezmoi diff --no-pager
chezmoi apply --force --no-tty
,agent-memory status
```

## AI knowledge base (`,ai-kb`)

`,ai-kb` ([`home/exact_bin/executable_,ai-kb`](../../../home/exact_bin/executable_,ai-kb) + [`scripts/ai_kb.py`](../../../scripts/ai_kb.py)) is the durable memory layer Ralph reads from and writes to. Capsules are markdown sidecars under `~/.local/share/ai-kb/capsules/<id>.md` (canonical content) plus an indexed SQLite mirror at `~/.local/share/ai-kb/kb.sqlite3` for retrieval. Schema is breaking by policy: when [`scripts/ai_kb.py::CAPSULE_COLUMNS`](../../../scripts/ai_kb.py) drifts from the on-disk shape, `init()` drops `capsules`/`capsule_fts`/`kb_meta` and recreates them — markdown sidecars survive so a curator (`,ai-kb ingest`) can re-hydrate.

Capsule shape:

| Field                                   | Purpose                                                                                             |
| --------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `kind`                                  | `fact` / `gotcha` / `pattern` / `anti_pattern` / `recipe` / `principle` / `doc`                     |
| `scope`                                 | `workspace` / `project` / `domain` / `universal` (controls reuse across runs and projects)          |
| `tags` / `domain_tags`                  | Free-form (TUI badges) and structured taxonomy (e.g. `auth`, `tmux`, `rust`)                        |
| `confidence` / `verified_by`            | Float 0-1 + role/run that verified it; reflectors and reviewers raise these                         |
| `supersedes` / `superseded_by`          | Bidirectional links built by `,ai-kb curate dedupe`; superseded capsules drop out of search         |
| `refs`                                  | Run / iteration / role / file refs so a hit can jump back to its origin                             |
| `embedding` / `embedding_model` / `dim` | Packed `float32` vector + provenance; populated via [`scripts/embed.py`](../../../scripts/embed.py) |
| `decay_score`                           | Incremented by `,ai-kb curate decay` for capsules nobody retrieves; surfaces stale memory           |

Retrieval is hybrid by default: lexical (FTS5/BM25) + dense (cosine over the embedding column, accelerated by `sqlite-vec`'s `vec0` virtual table) fused with Reciprocal Rank Fusion, then diversified with Maximal Marginal Relevance and filtered by `kind` / `scope` / `workspace_path` / `domain_tags`. Workspace matches give a soft RRF boost so project-scoped capsules outrank global ones for the active workspace. Superseded capsules are excluded by default. See [`KnowledgeBase.search`](../../../scripts/ai_kb.py).

Embeddings are computed by [`scripts/embed_runner.py`](../../../scripts/embed_runner.py) — a PEP 723 inline-deps script (`uv run --script`) that loads `fastembed` (`BAAI/bge-small-en-v1.5`, 384-d) on demand. The orchestrator stays stdlib-only; `Embedder` (in [`scripts/embed.py`](../../../scripts/embed.py)) shells out via JSON over stdin/stdout. `RALPH_KB_DISABLE_EMBED=1` skips embedding (used by the test suite + offline boxes; lexical retrieval still works).

Vector search and curate-pairs use the same subprocess-isolation pattern: [`scripts/vec_runner.py`](../../../scripts/vec_runner.py) is a PEP 723 inline-deps script that loads `sqlite-vec` and serves KNN / pairs queries against the KB SQLite file. The runner manages its own `vec_index` virtual table — lazily created from `capsules.embedding` BLOBs on first call and delta-synced on every subsequent call — so the orchestrator process never needs to load extensions (Apple's stock `python3` ships without `enable_load_extension`). Hard-fail by design: vec_runner errors raise `RuntimeError` rather than silently degrading to BM25-only. `RALPH_KB_DISABLE_VEC=1` is the test/offline escape hatch (mirrors `RALPH_KB_DISABLE_EMBED`). Curation's pairwise dedupe / contradiction-scan loop also goes through vec_runner — KNN-shortlist + per-pair cosine — replacing what was an O(N²) Python loop, so the curator scales with the KB.

Memory flow during a Ralph run:

1. Each role's prompt builder calls `KnowledgeBase.search(...)` filtered to that role's preferred kinds. Planner gets the broadest slice (no kind filter — anything prior may influence planning, with workspace bias surfacing project-local capsules first). Executor: `fact / recipe / gotcha / anti_pattern / pattern`. Reviewer: `gotcha / anti_pattern`. Re_reviewer: `gotcha / anti_pattern / principle`. Hits are injected into a `## RECENT LEARNINGS` block in the role prompt and a compressed copy is persisted to `manifest.json::roles[*].retrieval_log` for TUI replay.
2. Roles can also call the KB on demand from inside their pane (`,ai-kb search "<q>" --kind gotcha,anti_pattern --json`) — see the `Tool: on-demand KB search` section in each prompt.
3. Roles emit `LEARNING:` lines (free-form `gotcha`/`principle`/`fact`/`decision`); `,ralph` parses these in [`RalphRunner.capture_learnings`](../../../scripts/ralph.py) and stores them with `kind` inferred from role and `scope=project` when a workspace is set.
4. After a passing run the dedicated `reflector` role distills the run into a small JSON list of structured capsules (see [`reflector.md`](../../../home/dot_config/ralph/prompts/reflector.md)) which are validated and persisted, giving the next run high-signal retrieval material.

CLI surface:

```bash
,ai-kb remember --title "Project rule" --body "Keep generated state out of git." \
                --kind principle --scope project --tags lint
,ai-kb search "tmux capture-pane reuse"           # hybrid (lexical + vector)
,ai-kb search --kind gotcha --scope project --json
,ai-kb get <capsule-id>                            # full body + metadata
,ai-kb ingest ./AGENTS.md ./docs                   # chunk markdown into kind=doc capsules; idempotent on sha256
,ai-kb reembed                                     # rebuild missing/stale embeddings
,ai-kb curate dedupe                               # mark near-duplicates as superseded
,ai-kb curate decay                                # bump decay_score on dormant capsules
,ai-kb curate contradiction                       # flag suspicious gotcha vs fact pairs
,ai-kb doctor                                      # capsule count, FTS sanity, embedding coverage
```

The Ralph TUI exposes the KB with a `K` keybinding: a modal launches `,ai-kb search ... --json` over stdin/stdout; navigation is `↑/↓`, `enter` to dispatch a search, `esc`/`q` to close. The status bar shows total capsule count (`KB:N`).

## Cross-agent memory (`ai-kb` skill)

Ralph is no longer the only consumer. The same durable KB is wired into every interactive harness through the `ai-kb` skill ([`home/exact_dot_agents/exact_skills/exact_ai-kb/readonly_SKILL.md`](../../../home/exact_dot_agents/exact_skills/exact_ai-kb/readonly_SKILL.md) -> `~/.agents/skills/ai-kb/SKILL.md`), reinforced by a short trigger pointer in each SOP entrypoint:

| Harness    | Skill discovery                                   | Entrypoint pointer                                                                               |
| ---------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| cursor-cli | `~/.agents/skills/`                               | [`~/AGENTS.md`](../../../home/readonly_AGENTS.md) "Durable Agent Memory"                         |
| pi         | `~/.agents/skills/` (via the `pi-skills` package) | covered by the skill (auto-loaded)                                                               |
| Claude     | `~/.claude/skills` -> `~/.agents/skills/`         | [`~/CLAUDE.md`](../../../home/readonly_AGENTS.md) section 4.3 (symlink to `~/AGENTS.md`)         |
| Gemini     | `~/.agents/skills/`                               | [`~/.gemini/GEMINI.md`](../../../home/readonly_AGENTS.md) section 4.3 (symlink to `~/AGENTS.md`) |
| OpenCode   | `~/.agents/skills/`                               | `~/.config/opencode/AGENTS.md` -> `~/AGENTS.md` (same pointer as cursor-cli)                     |

Persistence stays agent-driven through the `,ai-kb` CLI — there is no auto-harvest and no MCP, so nothing writes to the KB without the agent's explicit `remember`. Retrieval is agent-driven too (the agent searches with its actual task — the highest-relevance query), but one hook now performs a **read-only** retrieval to seed context: `session_context.py` runs a relevance-gated `,ai-kb search` at `sessionStart` and injects up to three matching capsules under a `### Relevant Learnings (,ai-kb)` block. This fires **only** for a deliberate named topic (the active topic is neither the generic `current` fallback nor a per-session `session-*` key) that has a non-empty `<topic>.txt` spec; the spec text is the query, the `bm25` lane keeps it embedder-free and fast inside the hook timeout, and only capsules that are local to the workspace or scoped `domain`/`universal` clear the gate (so a large or cross-project KB cannot stuff the context). Ad-hoc/`session-*` and review topics get no warm-start. Cursor cannot inject context per-turn (`beforeSubmitPrompt` output is only `{continue, user_message}` and any `additional_context` there is dropped), so `sessionStart` is the only injection point; mid-task relevance comes from the agent's own searches. Persistence is the SOP's end-of-turn capture habit (`~/CLAUDE.md` §4.3): the agent self-vets and writes inline as the last step of a substantive turn, with no hook and no auto-submitted prompt.

Pi uses its own TypeScript extension API rather than the `hooks.json` lifecycle, so its recall lives in [`home/dot_pi/agent/extensions/ai-kb-recall.ts`](../../../home/dot_pi/agent/extensions/ai-kb-recall.ts). It is a thin delegating extension: topic + spec resolution comes from `,agent-memory status --json` (single source of truth in [`scripts/agent_memory.py`](../../../scripts/agent_memory.py)), and retrieval comes from `,ai-kb search`. All of pi's injection points use `before_agent_start` (pi's only context-injection hook): on the first prompt it injects the verification-discipline prefix (parity with `session_context.py`) and does the **same gated warm-start** as Cursor (named topic + spec query, `bm25`, the workspace/`domain`/`universal` scope gate, ≤3 capsules), and on every substantive prompt it does **per-turn retrieval using the actual prompt as the query** — the highest-relevance signal — deduped against capsules already injected this session. Per-turn injection is possible in pi precisely because `before_agent_start` can return an injected `message`, which Cursor's `beforeSubmitPrompt` cannot.

Cross-runtime durable-memory retrieval:

| Runtime               | Auto-retrieval mechanism                                                                 |
| --------------------- | ---------------------------------------------------------------------------------------- |
| Ralph                 | Mechanical push: top-K per role injected into the `## RECENT LEARNINGS` prompt block     |
| Cursor CLI / Claude   | `session_context.py` gated `sessionStart` warm-start (named topic only); else agent-pull |
| Pi                    | `ai-kb-recall.ts` warm-start (parity) **plus** per-turn prompt-query injection           |
| Gemini / Cursor cloud | No injection point available; agent-pull only                                            |

- **Read:** the `sessionStart` warm-start above seeds named-topic sessions automatically (pi also injects per prompt); beyond that, agents run `,ai-kb search "<q>" --limit 5 --json` (with `--kind` / `--scope` / `--workspace` / `--domain` / `--mode` filters) before non-trivial work, and `,ai-kb get <id> --json` to pull a full capsule.
- **Write:** agents call `,ai-kb remember --title ... --body ... --kind ... --scope ...` only for verified, durable, reusable insights — the same quality bar as Ralph's `LEARNING:` lines. Guesses and session-only notes stay out of the KB (those belong in `,agent-memory`).

The division of labor is explicit so agents do not confuse the two memory layers or the code index:

- `,ai-kb` (this skill) — durable cross-session knowledge.
- `,agent-memory` — ephemeral per-session working context under `/tmp/specs`.
- `semantic-code-search` skill (SCSI) — semantic code search over a repo, not memory.

All interactive harnesses (cursor-cli, pi, Claude, Gemini, OpenCode) are wired for skill-based access (agent-pull); Ralph remains wired through its role prompts. Automatic retrieval-injection is narrower — only the runtimes in the cross-runtime table above (Ralph, cursor-cli/Claude, pi) have an injection point; Gemini and OpenCode rely on agent-pull alone.

## Related

- [Ralph orchestrator](ralph.md) — the primary producer/consumer of the AI KB
- [The Agentic Operating System](index.md) — governance layer and skills
