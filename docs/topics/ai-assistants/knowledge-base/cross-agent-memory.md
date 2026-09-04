---
sidebar_position: 3
title: Runtime recall wiring
---

# Runtime recall wiring

Wiring that lets every governed harness **read** the durable KB with bounded automatic recall. **Writes are always explicit** (`,ai-kb remember`); hooks never auto-write capsules. Skill contract: `~/.agents/skills/k-ai-kb/SKILL.md`.

## Persistence vs injection

| Path      | Behavior                                                                                                               |
| --------- | ---------------------------------------------------------------------------------------------------------------------- |
| Explicit  | `,ai-kb search` / `get` / `remember` — run by the `k-agent-smol` operator; parent-inline only in the no-spawn fallback |
| Automatic | Only where a safe context-injection channel exists; gated and capped                                                   |

Runtimes without injection (e.g. Cursor cloud) retain the explicit `k-agent-smol`-mediated path only.

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
| Antigravity  | first `PreInvocation`                              | explicit search only    | `PostToolUse`         | Camel-case payloads; `injectSteps[].ephemeralMessage`; no per-turn prompt hook             |
| Cursor cloud | none                                               | none                    | none                  | Explicit agent-pull only                                                                   |

Shared prefix source: [`prefix.txt`](../../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt). Custom subagent profiles render it directly; manual tmux prompt wrapping uses the same text.

Without warm-up signal: session context includes `### Recall Notice` (delegate mid-task recall queries to `k-agent-smol`). `AI_AGENT_DEPTH=fast` skips warm-up and per-turn retrieval.

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

## Per-turn recall: staged candidates, k-agent-smol judgment

`perturn_recall.py` / Pi + OMP `ai-kb-recall.ts` — `hybrid` mode as the candidate filter:

| Gate                | Value                                                                                                                                                                                                                  |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Query               | current prompt                                                                                                                                                                                                         |
| Absolute cosine     | ≥ `0.55` (best row, not rank-0 — RRF order is relevance-blind)                                                                                                                                                         |
| Relative tail floor | `0.85` of best cosine (`0.60` for BM25 warm-start)                                                                                                                                                                     |
| Scope               | workspace-local, `domain`, `universal` via `--workspace-gate`                                                                                                                                                          |
| Connect-only        | `AI_EMBED_CONNECT_ONLY=1`; unavailable worker → omit block, continue                                                                                                                                                   |
| Cold re-warm        | ≥1 row and none carries `cosine_score` → fire detached best-effort `embed_client.py ensure` (flock-guarded) so a later turn regains the dense lane; this turn still stages nothing; an empty result set never fires it |

Capsule bodies are never injected per-turn. Gate-passing rows go in full to `.recall-candidates-<session-key>.json`, and the hook injects a `### ,ai-kb candidates staged` pointer only when at least one candidate id is new to the session (`.recall-staged-<session-key>.json` ledger). The pointer names the candidates file plus the session-state paths (topic spec + worklog), so the judge never guesses its inputs; sessions without a session key stage nothing and degrade to the pull path. The parent delegates judgment to the `k-agent-smol` subagent ([operator contract](../../../../home/exact_dot_agents/exact_skills/exact_k-ai-kb/exact_references/readonly_smol-operator.md)): counterfactual test against the topic spec + worklog tail, return of ≤3 admitted lines or `NONE`, admitted ids appended to `.recall-seen-<session-key>.json`. Ids the hook filters out: seen ids (already admitted) never re-stage; staged-but-unadmitted ids never re-point but stay pullable through a `k-agent-smol` recall query (the operator runs `,ai-kb search`/`get` in its own context). Delegation route per surface: the harness's named `k-agent-smol` profile where reachable; otherwise a harness-CLI one-shot on the memory-category model (e.g. `cursor-agent --model <memory pick> --print` — Cursor sessions whose Task schema exposes only the fixed generic subagent set cannot reach `k-agent-smol`); inline application of the operator contract only when no isolated spawn exists (see the `k-ai-kb` skill). The staged pointer itself names this fallback route and forbids substituting a generic subagent type, so a fixed-enum session goes straight to the one-shot instead of burning failed Task spawns.

Queries travel over stdin and are never written to process arguments. Tail trimming drops weak rows without reordering BM25 or fused/MMR results. Correction patterns may inject an anti-pattern note directive; durable writes still require verified `remember`.

## Depth profiles (`AI_AGENT_DEPTH`)

Unset/invalid → `balanced`.

| Depth      | BM25 startup | Resident warm-up | Fetch    | Prompt cap (chars) | Timeout |
| ---------- | ------------ | ---------------- | -------- | ------------------ | ------- |
| `fast`     | yes          | skipped          | disabled | —                  | —       |
| `balanced` | yes          | requested        | 6        | 600                | 6s      |
| `deep`     | yes          | requested        | 12       | 1200               | 9s      |

`fast` removes per-turn retrieval, not thresholds. Budgets fixture-backed: [`recall_worklog_state_machine.py`](../../../../scripts/tests/recall_worklog_state_machine.py). `AI_KB_RECALL_TIMEOUT` can raise per-turn timeout only.

## Store boundaries

`,ai-kb` is the sole durable semantic store. Codex auto-memory pinned off (`memories = false`). `/tmp/specs` archived daily to `~/.local/share/agent-specs-archive/` (raw preservation; no auto-KB write).

## Sources and verification

- [`exact_k-ai-kb/readonly_SKILL.md`](../../../../home/exact_dot_agents/exact_skills/exact_k-ai-kb/readonly_SKILL.md)
- [`ai-kb-recall.ts`](../../../../home/dot_pi/agent/exact_extensions/ai-kb-recall.ts), `~/.agents/hooks/perturn_recall.py`
- [`scripts/tests/recall_worklog_state_machine.py`](../../../../scripts/tests/recall_worklog_state_machine.py)
