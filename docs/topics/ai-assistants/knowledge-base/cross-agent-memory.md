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
| Cursor       | `sessionStart`; `AI_EMBED_WARM=1`                  | `beforeSubmitPrompt`    | shell/tool/edit hooks | Top-level `additional_context`; 10,000 UTF-16-unit carrier                                 |
| Claude       | `SessionStart`; `AI_EMBED_WARM=1`                  | `UserPromptSubmit`      | `PostToolUse*`        | Local llama.cpp settings excluded                                                          |
| Codex        | `SessionStart`; `AI_EMBED_WARM=1`                  | `UserPromptSubmit`      | `PostToolUse`         | Absolute paths, shell wrappers, hook-specific output; re-trust after hook changes          |
| Copilot      | SDK `onSessionStart`; payload warm-up              | `onUserPromptSubmitted` | `onPostToolUse*`      | Parent-session env affects subagent writes and `status`/`note`; startup recall stays blind |
| OpenCode     | system transform; payload warm-up                  | `chat.message`          | `tool.execute.after`  | Adapter synthesizes the shared payload shape                                               |
| Pi           | `session_start` ensure; first `before_agent_start` | `before_agent_start`    | `tool_result`         | Uses session-aware `,agent-memory status --json`                                           |
| OMP          | `session_start` ensure; first `before_agent_start` | `before_agent_start`    | `tool_result`         | Uses session-aware `,agent-memory status --json`                                           |
| Antigravity  | first `PreInvocation`                              | explicit search only    | `PostToolUse`         | Camel-case payloads; `injectSteps[].ephemeralMessage`; no per-turn prompt hook             |
| Cursor cloud | none                                               | none                    | none                  | Explicit agent-pull only                                                                   |

Shared reinforcement source: [`prefix.txt`](../../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt), a compiler-verified excerpt of the SOP. `perturn_recall.py` re-injects it only after material context growth (200k tokens read from the Claude transcript or Codex rollout; a prompt-interval fallback where no usage signal exists) or a compaction, so it lands near the current prompt exactly when the top-of-context rules have diluted. Session start injects no prefix. Custom subagent profiles render the sibling `leaf-boundary.txt`; manual tmux prompt wrapping uses `prefix.txt`.

Re-reads: a second whole-file read whose bytes match an earlier read in the same context is refused with a pointer to that read, but only after the recorded result of that read is found intact in the transcript (truncated, missing, or garbled history re-reads silently); a changed file is allowed with a staleness note. Child agents keep their own ledger, and a compaction resets it. Escape with offset/limit, `sed -n`, or `AGENT_READ_GATE=off`.

Topic binding: feature-branch sessions auto-bind to the newest bucket (or keep `current`) at session start with no model turn; default-branch sessions keep the bucket picker, bind in the same tool batch as their first command, or bind automatically when the prompt names a bucket. The judge pointer waits for the binding so it fires once per session.

Without warm-up signal: session context includes `### Recall Notice` (delegate mid-task recall queries to `k-agent-smol`). `AI_AGENT_DEPTH=fast` skips startup retrieval, warm-up, and per-turn retrieval. Cursor omits whole optional context blocks with source pointers to fit its carrier; mandatory instructions stay complete.

## Startup warm-start (BM25 only)

Gates in `session_context.py` — all must pass:

| Gate   | Rule                                                                      |
| ------ | ------------------------------------------------------------------------- |
| Topic  | Named via `.session-topic-<id>.txt`; not `current` or `session-*`         |
| Spec   | Non-empty `<topic>.txt` becomes query                                     |
| Lane   | BM25 only; no embedder in hook timeout                                    |
| Scope  | workspace-local, `domain`, or `universal`                                 |
| Output | ≤3 full capsule rows staged for isolated judgment; no raw bodies injected |

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

Capsule bodies are never injected by startup or per-turn hooks. Full gate-passing rows go to `.recall-candidates-<session-key>.json`; a bounded topic-specific `.recall-warm-<session-key>.json` cache preserves up to three startup rows across the first per-turn staging pass. The hook emits a `### ,ai-kb candidates staged` pointer once per observed session-topic binding when candidates exist. The pointer names the candidates file, topic spec, and worklog; keyless sessions stage nothing and use explicit recall. `.recall-pointed-<session-key>.json` records the observed topic and pointer state, including transitions through topics with no candidates. Same-binding later turns update candidates without another pointer; `.recall-staged-<session-key>.json` records staged IDs. Only `k-agent-smol` admissions update `.recall-seen-<session-key>.json`; hooks never mark candidates admitted.

The parent delegates judgment to `k-agent-smol` ([operator contract](../../../../home/exact_dot_agents/exact_skills/exact_k-ai-kb/exact_references/readonly_smol-operator.md)): counterfactual test against the topic spec and worklog tail, return ≤3 admitted lines or `NONE`. Already admitted IDs never re-stage; unadmitted candidates remain available through the operator's explicit recall query. Use the named profile where reachable; otherwise spawn a generic isolated subagent with the memory-category selection and full operator contract. Cursor's fixed Task schema uses `subagent_type: shell`, `model: auto`. NEVER use a harness-CLI one-shot for judge/scribe work; parent-inline fallback applies only when no isolated spawn exists, as defined by `k-ai-kb`.

Queries travel over stdin and are never written to process arguments. Tail trimming drops weak rows without reordering BM25 or fused/MMR results. Correction patterns may inject an anti-pattern note directive; durable writes still require verified persistence through the smol scribe route.

## Depth profiles (`AI_AGENT_DEPTH`)

Unset/invalid → `balanced`.

| Depth      | BM25 startup | Resident warm-up | Fetch    | Prompt cap (chars) | Timeout |
| ---------- | ------------ | ---------------- | -------- | ------------------ | ------- |
| `fast`     | no           | skipped          | disabled | —                  | —       |
| `balanced` | yes          | requested        | 6        | 600                | 6s      |
| `deep`     | yes          | requested        | 12       | 1200               | 9s      |

`fast` removes automatic retrieval; enabled profiles retain the same thresholds. Budgets fixture-backed: [`recall_worklog_state_machine.py`](../../../../scripts/tests/recall_worklog_state_machine.py). `AI_KB_RECALL_TIMEOUT` can raise per-turn timeout only.

Disabling hook context through the environment or sentinels suppresses every injection path, including corrections and compaction rehydration, while worklog recording and native SOP loading continue. Pi/OMP keep shared callbacks registered when the KB CLI is unavailable; only optional retrieval and warm-up are skipped.

## Store boundaries

`,ai-kb` is the sole durable semantic store. Codex auto-memory pinned off (`memories = false`). `/tmp/specs` archived daily to `~/.local/share/agent-specs-archive/` (raw preservation; no auto-KB write).

## Sources and verification

- [`exact_k-ai-kb/readonly_SKILL.md`](../../../../home/exact_dot_agents/exact_skills/exact_k-ai-kb/readonly_SKILL.md)
- [`ai-kb-recall.ts`](../../../../home/dot_pi/agent/exact_extensions/ai-kb-recall.ts), `~/.agents/hooks/perturn_recall.py`
- [`scripts/tests/recall_worklog_state_machine.py`](../../../../scripts/tests/recall_worklog_state_machine.py)
