---
sidebar_position: 3
title: Cross-agent memory
---

# Cross-agent memory (`k-ai-kb` skill)

Cross-agent memory is the wiring that lets every governed harness use the durable `,ai-kb` store without giving hooks permission to write capsules automatically. The `k-ai-kb` skill is the agent-facing contract; hooks and plugins only provide bounded recall when the runtime has a safe injection point. This page covers skill discovery, retrieval gates, runtime-specific injection, and the resident embedder path.

The moving parts:

| Piece                                                                                                                                                  | Role                                                                                                |
| ------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| [`home/exact_dot_agents/exact_skills/exact_k-ai-kb/readonly_SKILL.md`](../../../../home/exact_dot_agents/exact_skills/exact_k-ai-kb/readonly_SKILL.md) | Source skill deployed to `~/.agents/skills/k-ai-kb/SKILL.md`                                        |
| `,ai-kb remember`                                                                                                                                      | Explicit durable write path; there is no auto-harvest, no MCP, and no write without an agent action |
| `session_context.py`                                                                                                                                   | Read-only named-topic startup warm-start, using BM25 only                                           |
| `~/.agents/hooks/perturn_recall.py`                                                                                                                    | Shared per-turn recall implementation for runtimes with a current-turn context channel              |
| [`home/dot_pi/agent/extensions/ai-kb-recall.ts`](../../../../home/dot_pi/agent/extensions/ai-kb-recall.ts)                                             | Pi-specific TypeScript recall extension                                                             |
| `/tmp/specs/<workspace>/.recall-seen-<session-key>.json`                                                                                               | Per-session capsule dedupe shared by startup and per-turn recall                                    |
| `AI_AGENT_DEPTH`                                                                                                                                       | Selects the bounded automatic-recall profile for Claude, Gemini, OpenCode, Copilot, and Pi          |

## Using it

Persistence stays agent-driven. Agents write only by calling `,ai-kb remember` with deliberate metadata, and the SOP end-of-turn habit is just a self-vetting rule: the agent writes inline as the last step of a substantive turn, with no hook and no auto-submitted prompt.

Retrieval is mostly agent-driven too. The normal read path is to search with the actual task as query, then fetch a full capsule when needed:

```bash
,ai-kb search "<q>" --limit 5 --json
,ai-kb get <id> --json
```

The search command also accepts `--kind`, `--scope`, `--workspace`, `--domain`, and `--mode` filters. Skill-based or explicit-path access (`agent-pull`) is available to cursor-cli, Pi, Claude, Gemini, OpenCode, Codex, and Copilot; Palantír panes use those same harness routes.

Agents call `,ai-kb remember` with deliberate `--kind`/`--scope`/`--source`/`--confidence`/`--domain` metadata only for verified, durable, reusable insights. Guesses and session-only notes stay out of the KB; those belong in `,agent-memory`.

Keep the three memory-like systems separate:

| System                                | Use for                                                  | Do not use for          |
| ------------------------------------- | -------------------------------------------------------- | ----------------------- |
| `,ai-kb` / `k-ai-kb`                  | durable cross-session knowledge                          | transient scratch notes |
| `,agent-memory`                       | ephemeral per-session working context under `/tmp/specs` | durable lessons         |
| `k-semantic-code-search` skill / SCSI | semantic code search over a repo                         | agent memory            |

Automatic retrieval injection is narrower than skill access. Runtimes without a safe context channel still have explicit search/write access, but they do not receive per-turn injected recall.

## Skill discovery

| Harness    | Skill discovery                                    | Entrypoint pointer                                                                                  |
| ---------- | -------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| cursor-cli | `~/.agents/skills/`                                | [`~/AGENTS.md`](../../../../home/readonly_AGENTS.md) "Durable Agent Memory"                         |
| pi         | `~/.agents/skills/` via the `pi-skills` package    | covered by the skill (auto-loaded)                                                                  |
| Claude     | `~/.claude/skills` → `~/.agents/skills/`           | [`~/CLAUDE.md`](../../../../home/readonly_AGENTS.md) section 4.1 (symlink to `~/AGENTS.md`)         |
| Gemini     | `~/.agents/skills/`                                | [`~/.gemini/GEMINI.md`](../../../../home/readonly_AGENTS.md) section 4.1 (symlink to `~/AGENTS.md`) |
| OpenCode   | `~/.agents/skills/`                                | `~/.config/opencode/AGENTS.md` → `~/AGENTS.md` (same pointer as cursor-cli)                         |
| Codex      | agent-pull by explicit `~/.agents/skills/...` path | `~/.codex/AGENTS.md` → `~/AGENTS.md`                                                                |
| Copilot    | `~/.copilot/skills` → `~/.agents/skills`           | `~/.copilot/copilot-instructions.md` → `~/AGENTS.md`                                                |

## Startup warm-start

The shared `session_context.py` hook performs read-only warm-start retrieval only when all of these gates pass:

| Gate                       | Behavior                                                                               |
| -------------------------- | -------------------------------------------------------------------------------------- |
| active topic is deliberate | selected by `.session-topic-<id>.txt`, not a generic `current` or fallback `session-*` |
| topic spec exists          | `<topic>.txt` is non-empty and becomes the query                                       |
| retrieval lane             | BM25 only, fast and embedder-free inside hook timeout                                  |
| allowed scopes             | workspace-local, `domain`, or `universal` capsules                                     |
| result count               | up to three capsules under `### Relevant Learnings (,ai-kb)`                           |

This named-topic capsule warm-start is BM25-only and does not load or contact the resident embedder. Resident model warm-up is a separate, explicit lifecycle used only by runtimes that also have per-turn retrieval.

Unbound, ad-hoc `session-*`, and review topics get no warm-start. Cursor cannot inject context per turn because `beforeSubmitPrompt` drops `additional_context`, so `sessionStart` is its only injection point. Cursor mid-task relevance comes from explicit agent searches, and its session context carries a `### Recall Notice` directing the agent to self-search mid-task.

## Per-runtime wiring

| Runtime      | Automatic retrieval mechanism                                                                                                                                                                      | Resident embedder startup                                                            |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Palantír     | Role panes use their configured harness memory behavior; close-out durable findings route through explicit `,ai-kb remember`                                                                       | Inherits the selected harness behavior                                               |
| Cursor CLI   | `session_context.py` gated BM25 `sessionStart` recall for session-bound named topics only; otherwise Topic Buckets / agent-pull                                                                    | None; Cursor has no per-turn context-injection path                                  |
| Codex        | `session_context.py` gated BM25 `SessionStart` recall plus depth-controlled per-turn `UserPromptSubmit` injection; otherwise agent-pull                                                            | Per-turn via `UserPromptSubmit` (`perturn_recall.py`); warm-up via `AI_EMBED_WARM=1` |
| Copilot      | `agent-memory` SDK extension calls `session_context.py` in `onSessionStart` and returns `additionalContext`, plus per-turn via `onUserPromptSubmitted` (`perturn_recall.py`); otherwise agent-pull | Explicit bounded warm-up in its session-start payload                                |
| Claude       | `session_context.py` gated BM25 startup recall plus per-turn via `UserPromptSubmit`                                                                                                                | Explicit bounded warm-up through `AI_EMBED_WARM=1`                                   |
| Pi           | `ai-kb-recall.ts` BM25 startup recall (parity) plus per-turn prompt-query injection                                                                                                                | Explicit bounded warm-up during `session_start`                                      |
| OpenCode     | `agent-memory.ts` plugin: BM25 startup recall in the system prompt plus per-turn via `chat.message`                                                                                                | Explicit bounded warm-up through `warm_embedder: true`                               |
| Gemini       | BM25 `SessionStart` recall plus per-turn via `BeforeAgent` (`additionalContext`)                                                                                                                   | Explicit bounded warm-up through `AI_EMBED_WARM=1`                                   |
| Cursor cloud | No injection point available; agent-pull only                                                                                                                                                      | None                                                                                 |

Runtime hook names for the shared per-turn path:

| Runtime     | Hook                                                   |
| ----------- | ------------------------------------------------------ |
| Claude Code | `UserPromptSubmit`                                     |
| Gemini      | `BeforeAgent`                                          |
| OpenCode    | `chat.message` delegates to the hook                   |
| Copilot     | `onUserPromptSubmitted` SDK hook delegates to the hook |

All shared per-turn hooks inject `additionalContext` into the current turn. They do not re-prompt the agent or start another request/response cycle.

Codex uses absolute-path hooks because codex spawns hook commands without a shell. Pi uses its own TypeScript extension API rather than `hooks.json`: it passes `ctx.sessionManager.getSessionId()` to `,agent-memory status --json --session-id <id>`, so warm-start resolves the same session-bound bucket as the shared hooks.

Pi uses `before_agent_start` for two paths:

| Moment                   | Injection                                                                           |
| ------------------------ | ----------------------------------------------------------------------------------- |
| First prompt             | verification prefix plus gated warm-start from session-aware `,agent-memory status` |
| Every substantive prompt | per-turn retrieval using the actual prompt as query                                 |

This works in Pi because `before_agent_start` can return an injected `message`; Cursor's `beforeSubmitPrompt` cannot.

## Retrieval gates

Per-turn retrieval uses `hybrid` mode — lexical plus vector plus MMR — and dedupes capsule IDs already injected this session. Pi persists those IDs under `/tmp/specs/<workspace>/.recall-seen-<session-key>.json`, using the canonical key returned by `,agent-memory status`, so extension reloads and session resumes do not re-inject the same capsules.

`~/.agents/hooks/perturn_recall.py` mirrors Pi's `ai-kb-recall.ts` gates:

| Gate                | Value                                               |
| ------------------- | --------------------------------------------------- |
| query               | current prompt                                      |
| mode                | `hybrid`                                            |
| absolute top-cosine | `0.55`                                              |
| relative tail floor | `0.85`                                              |
| scope               | workspace-local, `domain`, or `universal`           |
| dedupe              | per-session seen-file dedupe shared with warm-start |

Per-turn `hybrid` retrieval has an absolute top-hit gate:

| Gate                         | Value / reason                                                                   |
| ---------------------------- | -------------------------------------------------------------------------------- |
| top `cosine_score` threshold | about `0.55`                                                                     |
| on-topic calibration         | live top hits scored `0.58-0.81`                                                 |
| off-topic calibration        | live top hits scored `0.44-0.48`                                                 |
| scope                        | the best `cosine_score` across ALL returned rows, not positionally the first row |
| mode                         | `hybrid` only; `bm25` has no cosine score                                        |

Hybrid rows are RRF+MMR fused-rank order, not best-cosine-first. The gate scans every row for the best available `cosine_score` instead of assuming row 0 holds it, because RRF rank position is relevance-blind. Without the gate, a prompt with no KB overlap could still inject equally irrelevant capsules.

Secondary hits are not individually cosine-filtered: legitimate secondary matches overlap the off-topic score range, so the relative floor trims the tail instead.

Both retrieval paths also apply a relative relevance floor:

| Rule               | Detail                                                                                                                                                                |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| best hit           | always kept — for `bm25` this is the positional top hit (rows are best-first); for `hybrid` it is whichever row holds the best `cosine_score`, regardless of position |
| tail cutoff        | drop hits below 60% (`bm25`/warm-start) or 85% (`hybrid`/per-turn) of the best hit's score                                                                            |
| presentation order | never reordered by score — the tail trim only drops rows, it does not resort the fused/MMR or bm25 order                                                              |
| `hybrid` signal    | `cosine_score` (`rrf_score` is rank-flat and cannot separate on-topic from cross-domain hits)                                                                         |
| `bm25` signal      | `bm25_score`                                                                                                                                                          |
| warm-start         | `session_context.py` applies the same `bm25` floor                                                                                                                    |

The scope gate is provenance-only. The relative floor prevents low-relevance capsules from filling open slots when fewer than three on-topic capsules exist.

## Depth profiles

`AI_AGENT_DEPTH` selects one bounded automatic-recall profile across Claude, Gemini, OpenCode, Copilot, and Pi. Unset, empty, or invalid values resolve to `balanced`.

| Depth      | Named-topic BM25 startup | Resident warm-up | Per-turn fetch / inject | Prompt cap | Body cap  | Timeout |
| ---------- | ------------------------ | ---------------- | ----------------------- | ---------- | --------- | ------- |
| `fast`     | unchanged                | skipped          | disabled                | n/a        | n/a       | n/a     |
| `balanced` | unchanged                | requested        | 6 / 3                   | 600 chars  | 240 chars | 6s      |
| `deep`     | unchanged                | requested        | 12 / 5                  | 1200 chars | 360 chars | 9s      |

The prompt cap is applied before appending the single ellipsis character. Every enabled profile keeps `hybrid` mode, the `0.55` absolute cosine gate, the `0.85` relative floor, workspace/domain/universal scope filtering enforced inside the KB via `,ai-kb search --workspace-gate`, canonical-session dedupe, query-over-stdin secrecy, and `AI_EMBED_CONNECT_ONLY=1`.

`fast` reduces work by removing per-turn retrieval rather than admitting weaker hits. `deep` spends more bounded retrieval and injection budget without changing relevance.

The profile budgets are fixture-backed in [`scripts/tests/recall_worklog_state_machine.py`](../../../../scripts/tests/recall_worklog_state_machine.py). With a deterministic 80ms search fixture, median hook latency measured 46.2ms for `fast`, 164.6ms for `balanced`, and 164.2ms for `deep`; unset measured 161.8ms with the same search arguments as `balanced`. The relevance thresholds remain calibrated at `0.58-0.81` on-topic versus `0.44-0.48` off-topic, and are not relaxed for either new mode.

## Internals (for maintainers)

### Connect-only hot path

The per-turn hot path is connect-only:

| Property                 | Contract                                                                                                                                             |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Deployed runtime         | `~/lib/,ai-kb/{main,agent_memory,embed,embed_runner,embed_client,embed_worker,vec_runner}.py`; `~/bin/,ai-kb` does not discover the chezmoi checkout |
| Session-start ownership  | Claude, Gemini, OpenCode, Copilot, and Pi may call bounded `ensure` in `balanced`/`deep`; `fast` skips it and all calls are fail-open                |
| Per-turn ownership       | `perturn_recall.py` and Pi set `AI_EMBED_CONNECT_ONLY=1`; they never spawn, restart, evict, or replace a worker                                      |
| Generation identity      | Protocol + complete worker source + model + expected dimension produce a generation-specific socket                                                  |
| Runtime isolation        | User-owned `0700` root, `0600` socket/start lock, bounded worker messages/deadlines; the worker never logs or echoes prompt text                     |
| Idle lifecycle           | The worker exits after 300 inactive seconds and removes only its own socket inode                                                                    |
| Unavailable/invalid path | The hook returns no recall context and the current request continues; default/manual/`remember`/`reembed` continue to use the one-shot runner        |

The default BGE-small worker measured about 320 MiB RSS; two coexisting deployment generations measured about 625 MiB total. The 300-second activity timeout bounds that temporary overlap.

### Store boundaries

`,ai-kb` remains the sole durable semantic store. Harness-native memory features stay unused; Codex's experimental auto-memory is pinned off via `[features] memories = false`.

Episodic `/tmp/specs` traces are snapshotted daily to `~/.local/share/agent-specs-archive/` via crontab rsync. The archive is raw preservation only; nothing auto-writes it to the KB.

## Sources and verification

- [`home/exact_dot_agents/exact_skills/exact_k-ai-kb/readonly_SKILL.md`](../../../../home/exact_dot_agents/exact_skills/exact_k-ai-kb/readonly_SKILL.md)
- [`home/dot_pi/agent/extensions/ai-kb-recall.ts`](../../../../home/dot_pi/agent/extensions/ai-kb-recall.ts)
- [`scripts/agent_memory.py`](../../../../scripts/agent_memory.py)
- [`scripts/tests/recall_worklog_state_machine.py`](../../../../scripts/tests/recall_worklog_state_machine.py)
- `~/.agents/hooks/perturn_recall.py`
