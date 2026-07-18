---
sidebar_position: 3
title: Runtime recall wiring
---

# Runtime recall wiring

Wiring that lets every governed harness **read** the durable KB with bounded automatic recall. **Writes are always explicit** (`,ai-kb remember`); hooks never auto-write capsules. Skill contract: `~/.agents/skills/k-ai-kb/SKILL.md`.

## Persistence vs injection

| Path      | Behavior                                                                  |
| --------- | ------------------------------------------------------------------------- |
| Explicit  | `,ai-kb search` / `get` / `remember` — any harness with CLI or agent-pull |
| Automatic | Only where a safe context-injection channel exists; gated and capped      |

Runtimes without injection (e.g. Cursor cloud) retain explicit search/write only.

## Harness matrix

Shared scripts: `session_context.py` (start), `perturn_recall.py` (per-turn), `worklog_dispatcher.sh` (post-tool). Adapters in repo under `home/dot_*` / `exact_hooks/`.

| Runtime      | Session start and warm-up                          | Per-turn recall         | Worklog               | Exception                                                                                  |
| ------------ | -------------------------------------------------- | ----------------------- | --------------------- | ------------------------------------------------------------------------------------------ |
| Cursor       | `sessionStart`; `AI_EMBED_WARM=1`                  | `beforeSubmitPrompt`    | shell/tool/edit hooks | Top-level `additional_context`; 10,000-character carrier                                   |
| Claude       | `SessionStart`; `AI_EMBED_WARM=1`                  | `UserPromptSubmit`      | `PostToolUse*`        | Local llama.cpp settings excluded                                                          |
| Codex        | `SessionStart`; `AI_EMBED_WARM=1`                  | `UserPromptSubmit`      | `PostToolUse`         | Absolute paths, shell wrappers, hook-specific output; re-trust after hook changes          |
| Copilot      | SDK `onSessionStart`; payload warm-up              | `onUserPromptSubmitted` | `onPostToolUse*`      | Parent-session env affects subagent writes and `status`/`note`; startup recall stays blind |
| OpenCode     | system transform; payload warm-up                  | `chat.message`          | `tool.execute.after`  | Adapter synthesizes the shared payload shape                                               |
| Pi           | `session_start` ensure; first `before_agent_start` | `before_agent_start`    | `tool_result`         | Uses session-aware `,agent-memory status --json`                                           |
| Gemini       | `SessionStart`; `AI_EMBED_WARM=1`                  | `BeforeAgent`           | `AfterTool`           |                                                                                            |
| Palantír     | inherits the configured harness                    | inherits harness        | inherits harness      | Close-out durable findings route through explicit `remember`                               |
| Cursor cloud | none                                               | none                    | none                  | Explicit agent-pull only                                                                   |

Shared prefix source: [`prefix.txt`](../../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt). Custom subagent profiles render it directly; manual tmux prompt wrapping uses the same text.

Without warm-up signal: session context includes `### Recall Notice` (self-search mid-task). `AI_AGENT_DEPTH=fast` skips warm-up and per-turn retrieval.

## Startup warm-start (BM25 only)

Gates in `session_context.py` — all must pass:

| Gate   | Rule                                                              |
| ------ | ----------------------------------------------------------------- |
| Topic  | Named via `.session-topic-<id>.txt`; not `current` or `session-*` |
| Spec   | Non-empty `<topic>.txt` becomes query                             |
| Lane   | BM25 only; no embedder in hook timeout                            |
| Scope  | workspace-local, `domain`, or `universal`                         |
| Output | ≤3 capsules under `### Relevant Learnings (,ai-kb)`               |

Review/unbound topics: no warm-start. Separate from resident embedder warm-up (per-turn path only).

## Per-turn recall gates

`perturn_recall.py` / Pi `ai-kb-recall.ts` — `hybrid` mode, dedupe via `.recall-seen-<session-key>.json`:

| Gate                | Value                                                                |
| ------------------- | -------------------------------------------------------------------- |
| Query               | current prompt                                                       |
| Absolute cosine     | ≥ `0.55` (best row, not rank-0 — RRF order is relevance-blind)       |
| Relative tail floor | `0.85` of best cosine (`0.60` for BM25 warm-start)                   |
| Scope               | workspace-local, `domain`, `universal` via `--workspace-gate`        |
| Connect-only        | `AI_EMBED_CONNECT_ONLY=1`; unavailable worker → omit block, continue |

Queries travel over stdin and are never written to process arguments. Tail trimming drops weak rows without reordering BM25 or fused/MMR results. Correction patterns may inject an anti-pattern note directive; durable writes still require verified `remember`.

## Depth profiles (`AI_AGENT_DEPTH`)

Unset/invalid → `balanced`.

| Depth      | BM25 startup | Resident warm-up | Fetch/inject | Prompt cap (chars) | Body cap (chars) | Timeout |
| ---------- | ------------ | ---------------- | ------------ | ------------------ | ---------------- | ------- |
| `fast`     | yes          | skipped          | disabled     | —                  | —                | —       |
| `balanced` | yes          | requested        | 6 / 3        | 600                | 240              | 6s      |
| `deep`     | yes          | requested        | 12 / 5       | 1200               | 360              | 9s      |

`fast` removes per-turn retrieval, not thresholds. Budgets fixture-backed: [`recall_worklog_state_machine.py`](../../../../scripts/tests/recall_worklog_state_machine.py). `AI_KB_RECALL_TIMEOUT` can raise per-turn timeout only.

## Store boundaries

`,ai-kb` is the sole durable semantic store. Codex auto-memory pinned off (`memories = false`). `/tmp/specs` archived daily to `~/.local/share/agent-specs-archive/` (raw preservation; no auto-KB write).

## Sources and verification

- [`exact_k-ai-kb/readonly_SKILL.md`](../../../../home/exact_dot_agents/exact_skills/exact_k-ai-kb/readonly_SKILL.md)
- [`ai-kb-recall.ts`](../../../../home/dot_pi/agent/extensions/ai-kb-recall.ts), `~/.agents/hooks/perturn_recall.py`
- [`scripts/tests/recall_worklog_state_machine.py`](../../../../scripts/tests/recall_worklog_state_machine.py)
