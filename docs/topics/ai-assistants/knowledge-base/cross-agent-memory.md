---
sidebar_position: 3
title: Cross-agent memory
---

# Cross-agent memory (`ai-kb` skill)

Interactive harnesses reach the durable KB through the `ai-kb` skill, and Palantír routes durable close-out findings through the same CLI:

| Surface | Path                                                                                                                                               |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source  | [`home/exact_dot_agents/exact_skills/exact_ai-kb/readonly_SKILL.md`](../../../../home/exact_dot_agents/exact_skills/exact_ai-kb/readonly_SKILL.md) |
| Target  | `~/.agents/skills/ai-kb/SKILL.md`                                                                                                                  |

| Harness    | Skill discovery                                    | Entrypoint pointer                                                                                  |
| ---------- | -------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| cursor-cli | `~/.agents/skills/`                                | [`~/AGENTS.md`](../../../../home/readonly_AGENTS.md) "Durable Agent Memory"                         |
| pi         | `~/.agents/skills/` (via the `pi-skills` package)  | covered by the skill (auto-loaded)                                                                  |
| Claude     | `~/.claude/skills` -> `~/.agents/skills/`          | [`~/CLAUDE.md`](../../../../home/readonly_AGENTS.md) section 4.1 (symlink to `~/AGENTS.md`)         |
| Gemini     | `~/.agents/skills/`                                | [`~/.gemini/GEMINI.md`](../../../../home/readonly_AGENTS.md) section 4.1 (symlink to `~/AGENTS.md`) |
| OpenCode   | `~/.agents/skills/`                                | `~/.config/opencode/AGENTS.md` -> `~/AGENTS.md` (same pointer as cursor-cli)                        |
| Codex      | agent-pull by explicit `~/.agents/skills/...` path | `~/.codex/AGENTS.md` -> `~/AGENTS.md`                                                               |
| Copilot    | `~/.copilot/skills` -> `~/.agents/skills`          | `~/.copilot/copilot-instructions.md` -> `~/AGENTS.md`                                               |

Persistence stays agent-driven through `,ai-kb remember`. There is no auto-harvest and no MCP, so nothing writes to the KB without an explicit agent action.

Retrieval is mostly agent-driven too: the agent searches with the actual task as query. The shared `session_context.py` hook performs read-only warm-start retrieval:

| Gate                       | Behavior                                                                               |
| -------------------------- | -------------------------------------------------------------------------------------- |
| active topic is deliberate | selected by `.session-topic-<id>.txt`, not a generic `current` or fallback `session-*` |
| topic spec exists          | `<topic>.txt` is non-empty and becomes the query                                       |
| retrieval lane             | BM25 only, fast and embedder-free inside hook timeout                                  |
| allowed scopes             | workspace-local, `domain`, or `universal` capsules                                     |
| result count               | up to three capsules under `### Relevant Learnings (,ai-kb)`                           |

This named-topic capsule warm-start is BM25-only and does not load or contact the resident embedder. Resident model warm-up is a separate, explicit lifecycle used only by runtimes that also have per-turn retrieval.

Unbound, ad-hoc `session-*`, and review topics get no warm-start. Cursor cannot inject context per turn (`beforeSubmitPrompt` drops `additional_context`), so `sessionStart` is the only injection point. Mid-task relevance comes from explicit agent searches.

Persistence is the SOP's end-of-turn habit: the agent self-vets and writes inline as the last step of a substantive turn, with no hook and no auto-submitted prompt.

Pi uses its own TypeScript extension API rather than `hooks.json`. It passes `ctx.sessionManager.getSessionId()` to `,agent-memory status --json --session-id <id>`, so warm-start resolves the same session-bound bucket as the shared hooks.

| Piece               | Source                                                                                                               |
| ------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Pi recall extension | [`home/dot_pi/agent/extensions/ai-kb-recall.ts`](../../../../home/dot_pi/agent/extensions/ai-kb-recall.ts)           |
| Topic/spec source   | `,agent-memory status --json --session-id <id>` via [`scripts/agent_memory.py`](../../../../scripts/agent_memory.py) |
| Retrieval source    | `,ai-kb search`                                                                                                      |
| Injection point     | `before_agent_start`                                                                                                 |

Pi uses `before_agent_start` for two paths:

| Moment                   | Injection                                                                           |
| ------------------------ | ----------------------------------------------------------------------------------- |
| First prompt             | verification prefix plus gated warm-start from session-aware `,agent-memory status` |
| Every substantive prompt | per-turn retrieval using the actual prompt as query                                 |

Per-turn retrieval uses `hybrid` mode — lexical + vector + MMR — and dedupes capsules already injected this session. Pi persists the injected capsule IDs under `/tmp/specs/<workspace>/.recall-seen-<session-key>.json`, using the canonical key returned by `,agent-memory status`, so extension reloads and session resumes do not re-inject the same capsules. This works in Pi because `before_agent_start` can return an injected `message`; Cursor's `beforeSubmitPrompt` cannot.

Per-turn (`hybrid`) retrieval has an **absolute top-hit gate**:

| Gate                         | Value / reason                                                                   |
| ---------------------------- | -------------------------------------------------------------------------------- |
| top `cosine_score` threshold | about `0.55`                                                                     |
| on-topic calibration         | live top hits scored `0.58-0.81`                                                 |
| off-topic calibration        | live top hits scored `0.44-0.48`                                                 |
| scope                        | the best `cosine_score` across ALL returned rows, not positionally the first row |
| mode                         | `hybrid` only; `bm25` has no cosine score                                        |

Hybrid rows are RRF+MMR fused-rank order, not best-cosine-first, so the gate scans every row for the best available `cosine_score` instead of assuming row 0 holds it. Without this gate, a prompt with no KB overlap could still inject equally irrelevant capsules because RRF rank position is relevance-blind.

Secondary hits are not individually cosine-filtered: legitimate secondary matches overlap the off-topic score range, so the relative floor trims the tail instead.

Both retrieval paths also apply a **relative relevance floor**:

| Rule               | Detail                                                                                                                                                                |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| best hit           | always kept — for `bm25` this is the positional top hit (rows are best-first); for `hybrid` it is whichever row holds the best `cosine_score`, regardless of position |
| tail cutoff        | drop hits below 60% (`bm25`/warm-start) or 85% (`hybrid`/per-turn) of the best hit's score                                                                            |
| presentation order | never reordered by score — the tail trim only drops rows, it does not resort the fused/MMR or bm25 order                                                              |
| `hybrid` signal    | `cosine_score` (`rrf_score` is rank-flat and cannot separate on-topic from cross-domain hits)                                                                         |
| `bm25` signal      | `bm25_score`                                                                                                                                                          |
| warm-start         | `session_context.py` applies the same `bm25` floor                                                                                                                    |

The scope gate is provenance-only. The relative floor prevents low-relevance capsules from filling open slots when fewer than three on-topic capsules exist.

Cross-runtime durable-memory retrieval:

| Runtime      | Automatic retrieval mechanism                                                                                                                                                                    | Resident embedder startup                              |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| Palantír     | Role panes use their configured harness memory behavior; close-out durable findings route through explicit `,ai-kb remember`                                                                     | Inherits the selected harness behavior                 |
| Cursor CLI   | `session_context.py` gated BM25 `sessionStart` recall (session-bound named topic only); else Topic Buckets / agent-pull                                                                          | None; Cursor has no per-turn context-injection path    |
| Codex        | `session_context.py` gated BM25 `SessionStart` recall; else agent-pull                                                                                                                           | None; Codex is not wired to per-turn recall            |
| Copilot      | `agent-memory` SDK extension calls `session_context.py` in `onSessionStart` and returns `additionalContext` **plus** per-turn via `onUserPromptSubmitted` (`perturn_recall.py`); else agent-pull | Explicit bounded warm-up in its session-start payload  |
| Claude       | `session_context.py` gated BM25 startup recall **plus** per-turn via `UserPromptSubmit`                                                                                                          | Explicit bounded warm-up through `AI_EMBED_WARM=1`     |
| Pi           | `ai-kb-recall.ts` BM25 startup recall (parity) **plus** per-turn prompt-query injection                                                                                                          | Explicit bounded warm-up during `session_start`        |
| OpenCode     | `agent-memory.ts` plugin: BM25 startup recall in the system prompt **plus** per-turn via `chat.message`                                                                                          | Explicit bounded warm-up through `warm_embedder: true` |
| Gemini       | BM25 `SessionStart` recall **plus** per-turn via `BeforeAgent` (`additionalContext`)                                                                                                             | Explicit bounded warm-up through `AI_EMBED_WARM=1`     |
| Cursor cloud | No injection point available; agent-pull only                                                                                                                                                    | None                                                   |

`~/.agents/hooks/perturn_recall.py` is the shared per-turn implementation.

It mirrors Pi's `ai-kb-recall.ts` gates:

| Gate                | Value                                              |
| ------------------- | -------------------------------------------------- |
| query               | current prompt                                     |
| mode                | `hybrid`                                           |
| absolute top-cosine | `0.55`                                             |
| relative tail floor | `0.85`                                             |
| scope               | workspace-local, `domain`, or `universal`          |
| dedupe              | per-session seen-file dedup shared with warm-start |

`AI_AGENT_DEPTH` selects one bounded automatic-recall profile across Claude, Gemini, OpenCode, Copilot, and Pi. Unset, empty, or invalid values resolve to `balanced`, preserving the pre-depth behavior.

| Depth      | Named-topic BM25 startup | Resident warm-up | Per-turn fetch / inject | Prompt cap | Body cap  | Timeout |
| ---------- | ------------------------ | ---------------- | ----------------------- | ---------- | --------- | ------- |
| `fast`     | unchanged                | skipped          | disabled                | n/a        | n/a       | n/a     |
| `balanced` | unchanged                | requested        | 6 / 3                   | 600 chars  | 240 chars | 6s      |
| `deep`     | unchanged                | requested        | 12 / 5                  | 1200 chars | 360 chars | 9s      |

The prompt cap is applied before appending the single ellipsis character. Every enabled profile keeps `hybrid` mode, the `0.55` absolute cosine gate, the `0.85` relative floor, workspace/domain/universal scope filtering, canonical-session dedupe, query-over-stdin secrecy, and `AI_EMBED_CONNECT_ONLY=1`. `fast` therefore reduces work by removing per-turn retrieval rather than admitting weaker hits; `deep` spends more bounded retrieval and injection budget without changing relevance.

The profile budgets are fixture-backed in [`scripts/tests/recall_worklog_state_machine.py`](../../../../scripts/tests/recall_worklog_state_machine.py). With a deterministic 80ms search fixture, median hook latency measured 46.2ms for `fast`, 164.6ms for `balanced`, and 164.2ms for `deep`; unset measured 161.8ms with the same search arguments as `balanced`. The relevance thresholds retain their earlier live calibration (`0.58-0.81` on-topic versus `0.44-0.48` off-topic) rather than being relaxed for either new mode.

Runtime hooks:

| Runtime     | Hook                                                   |
| ----------- | ------------------------------------------------------ |
| Claude Code | `UserPromptSubmit`                                     |
| Gemini      | `BeforeAgent`                                          |
| OpenCode    | `chat.message` delegates to the hook                   |
| Copilot     | `onUserPromptSubmitted` SDK hook delegates to the hook |

All of these inject `additionalContext` into the current turn. They do not re-prompt the agent or start another request/response cycle.

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

`,ai-kb` remains the sole durable semantic store. Harness-native memory features stay unused; Codex's experimental auto-memory is pinned off via `[features] memories = false`.

Episodic `/tmp/specs` traces are snapshotted daily to `~/.local/share/agent-specs-archive/` via crontab rsync. The archive is raw preservation only; nothing auto-writes it to the KB.

- **Read:** the `sessionStart` warm-start above seeds named-topic sessions automatically (pi also injects per prompt); beyond that, agents run `,ai-kb search "<q>" --limit 5 --json` (with `--kind` / `--scope` / `--workspace` / `--domain` / `--mode` filters) before non-trivial work, and `,ai-kb get <id> --json` to pull a full capsule.
- **Write:** agents call `,ai-kb remember` (with deliberate `--kind`/`--scope`/`--source`/`--confidence`/`--domain` per the skill's write contract) only for verified, durable, reusable insights — the same quality bar as any durable close-out finding. Guesses and session-only notes stay out of the KB (those belong in `,agent-memory`).

The division of labor is explicit so agents do not confuse the two memory layers or the code index:

- `,ai-kb` (this skill) — durable cross-session knowledge.
- `,agent-memory` — ephemeral per-session working context under `/tmp/specs`.
- `semantic-code-search` skill (SCSI) — semantic code search over a repo, not memory.

Interactive harnesses are wired for skill-based or explicit-path access (`agent-pull`): cursor-cli, Pi, Claude, Gemini, OpenCode, Codex, and Copilot. Palantír panes use those same harness routes.

Automatic retrieval injection is narrower than skill access:

- Palantír role panes use the configured harness route for retrieval and route durable close-out findings through `,ai-kb remember`.
- cursor-cli/Codex use BM25 session-start recall only and never warm the resident embedder.
- Pi uses BM25 startup recall plus depth-controlled per-turn prompt retrieval and warms the resident embedder in `balanced`/`deep`.
- Claude, Gemini, OpenCode, and Copilot use BM25 startup recall plus depth-controlled per-turn hook injection and warm the resident embedder in `balanced`/`deep`.
- Cursor cloud uses explicit agent-pull only.
