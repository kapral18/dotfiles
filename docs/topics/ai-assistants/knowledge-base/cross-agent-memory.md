---
sidebar_position: 3
title: Cross-agent memory
---

# Cross-agent memory (`ai-kb` skill)

Ralph is no longer the only consumer. Interactive harnesses reach the same durable KB through the `ai-kb` skill:

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

| Gate                         | Value / reason                            |
| ---------------------------- | ----------------------------------------- |
| top `cosine_score` threshold | about `0.55`                              |
| on-topic calibration         | live top hits scored `0.58-0.81`          |
| off-topic calibration        | live top hits scored `0.44-0.48`          |
| scope                        | top hit only                              |
| mode                         | `hybrid` only; `bm25` has no cosine score |

Without this gate, a prompt with no KB overlap could still inject equally irrelevant capsules because RRF rank position is relevance-blind.

Secondary hits are not individually cosine-filtered: legitimate secondary matches overlap the off-topic score range, so the relative floor trims the tail instead.

Both retrieval paths also apply a **relative relevance floor**:

| Rule            | Detail                                             |
| --------------- | -------------------------------------------------- |
| top hit         | always kept                                        |
| tail cutoff     | drop hits below 60% of the best hit's score        |
| `hybrid` signal | `rrf_score`                                        |
| `bm25` signal   | `bm25_score`                                       |
| warm-start      | `session_context.py` applies the same `bm25` floor |

The scope gate is provenance-only. The relative floor prevents low-relevance capsules from filling open slots when fewer than three on-topic capsules exist.

Cross-runtime durable-memory retrieval:

| Runtime      | Auto-retrieval mechanism                                                                                                                                                                         |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Ralph        | Mechanical push: top-K per role injected into the `## RECENT LEARNINGS` prompt block                                                                                                             |
| Cursor CLI   | `session_context.py` gated `sessionStart` warm-start (session-bound named topic only); else Topic Buckets / agent-pull                                                                           |
| Codex        | `session_context.py` gated `SessionStart` warm-start; else agent-pull                                                                                                                            |
| Copilot      | `agent-memory` SDK extension calls `session_context.py` in `onSessionStart` and returns `additionalContext` **plus** per-turn via `onUserPromptSubmitted` (`perturn_recall.py`); else agent-pull |
| Claude       | `session_context.py` gated `sessionStart` warm-start **plus** per-turn via `UserPromptSubmit`                                                                                                    |
| Pi           | `ai-kb-recall.ts` warm-start (parity) **plus** per-turn prompt-query injection                                                                                                                   |
| OpenCode     | `agent-memory.ts` plugin: warm-start in system prompt **plus** per-turn via `chat.message`                                                                                                       |
| Gemini       | `SessionStart` warm-start **plus** per-turn via `BeforeAgent` (`additionalContext`)                                                                                                              |
| Cursor cloud | No injection point available; agent-pull only                                                                                                                                                    |

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

Runtime hooks:

| Runtime     | Hook                                                   |
| ----------- | ------------------------------------------------------ |
| Claude Code | `UserPromptSubmit`                                     |
| Gemini      | `BeforeAgent`                                          |
| OpenCode    | `chat.message` delegates to the hook                   |
| Copilot     | `onUserPromptSubmitted` SDK hook delegates to the hook |

All of these inject `additionalContext` into the current turn. They do not re-prompt the agent or start another request/response cycle.

`,ai-kb` remains the sole durable semantic store. Harness-native memory features stay unused; Codex's experimental auto-memory is pinned off via `[features] memories = false`.

Episodic `/tmp/specs` traces are snapshotted daily to `~/.local/share/agent-specs-archive/` via crontab rsync. The archive is raw preservation only; nothing auto-writes it to the KB.

- **Read:** the `sessionStart` warm-start above seeds named-topic sessions automatically (pi also injects per prompt); beyond that, agents run `,ai-kb search "<q>" --limit 5 --json` (with `--kind` / `--scope` / `--workspace` / `--domain` / `--mode` filters) before non-trivial work, and `,ai-kb get <id> --json` to pull a full capsule.
- **Write:** agents call `,ai-kb remember` (with deliberate `--kind`/`--scope`/`--source`/`--confidence`/`--domain` per the skill's write contract) only for verified, durable, reusable insights — the same quality bar as Ralph's `LEARNING:` lines. Guesses and session-only notes stay out of the KB (those belong in `,agent-memory`).

The division of labor is explicit so agents do not confuse the two memory layers or the code index:

- `,ai-kb` (this skill) — durable cross-session knowledge.
- `,agent-memory` — ephemeral per-session working context under `/tmp/specs`.
- `semantic-code-search` skill (SCSI) — semantic code search over a repo, not memory.

Interactive harnesses are wired for skill-based or explicit-path access (`agent-pull`): cursor-cli, Pi, Claude, Gemini, OpenCode, Codex, and Copilot. Ralph remains wired through role prompts.

Automatic retrieval injection is narrower than skill access:

- Ralph injects mechanically per role.
- cursor-cli/Codex use session warm-start only.
- Pi uses warm-start plus per-turn prompt retrieval.
- Claude, Gemini, OpenCode, and Copilot use warm-start plus per-turn hook injection.
- Cursor cloud uses explicit agent-pull only.
