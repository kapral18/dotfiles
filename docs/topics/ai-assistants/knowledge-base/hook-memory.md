---
sidebar_position: 1
title: Hook memory
---

# Hook memory (`/tmp/specs`, `,agent-memory`)

Cursor CLI is the primary interactive assistant harness.

| Surface             | Source                                                                                 | Target                 |
| ------------------- | -------------------------------------------------------------------------------------- | ---------------------- |
| Cursor hooks        | [`home/dot_cursor/hooks.json`](../../../../home/dot_cursor/hooks.json)                 | `~/.cursor/hooks.json` |
| Shared hook scripts | [`home/exact_dot_agents/exact_hooks/`](../../../../home/exact_dot_agents/exact_hooks/) | `~/.agents/hooks/`     |

The hook layer is Cursor-native first:

| Event                                                                       | Script                  | Purpose                                                                                                                                                                                                                                                                                                                                                       |
| --------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sessionStart`                                                              | `session_context.py`    | Inject the verification-discipline prefix (`prefix.txt`); show a bounded topic-bucket index until the session is bound; inject the selected `/tmp/specs` topic spec plus recent worklog tail when present; remind to recall/remember durable knowledge via `,ai-kb`; perform a bounded resident-embedder warm-up only when the adapter explicitly requests it |
| `afterShellExecution`, `postToolUse`, `postToolUseFailure`, `afterFileEdit` | `worklog_dispatcher.sh` | Capture stdin, launch the bounded queue recorder off the tool critical path, and return without waiting for worklog I/O                                                                                                                                                                                                                                       |

OpenCode reuses both scripts through [`agent-memory.ts`](../../../../home/dot_config/opencode/plugins/agent-memory.ts) (the plugin also wires a third hook for per-turn AI-KB recall — see [Cross-agent memory](cross-agent-memory.md)):

| OpenCode hook                        | What it does                                                                                                                      |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| `experimental.chat.system.transform` | Fetches `session_context.py` once per session with `warm_embedder: true` and appends its context to every request's system prompt |
| `tool.execute.after`                 | Feeds `worklog_dispatcher.sh` a synthesized `PostToolUse` payload with OpenCode's `sessionID`                                     |

`duration` and `status` are not exposed by the OpenCode plugin API and are omitted.

Codex has the same wiring in [`home/dot_codex/hooks.json`](../../../../home/dot_codex/hooks.json):

| Codex event    | Script                  |
| -------------- | ----------------------- |
| `SessionStart` | `session_context.py`    |
| `PostToolUse`  | `worklog_dispatcher.sh` |

Payload shapes are Claude-compatible as of codex source tag `rust-v0.139.0`. Hook trust hashes are baked into config templates because the codex merge script regenerates `config.toml` wholesale.

Codex does not request resident-embedder warm-up: it has session-start BM25 retrieval but no per-turn recall adapter. Cursor follows the same split.

**Caveat:** `,codex exec` 0.139.0 was verified to dispatch no hooks, even with `--dangerously-bypass-hook-trust` and `[features] hooks = true`. This wiring is currently inert in exec mode. For interactive TUI sessions, run `/hooks` and verify both hooks are trusted and fire.

No hook runs on `stop`. Hooks observe and inject context; they do not re-prompt the agent. Two disciplines that earlier lived in `stop` hooks now live in the SOP, enforced by instruction rather than by an auto-submitted follow-up message:

- **Evidence anchoring** — a factual/runtime claim must carry a hard source anchor (file path, command/probe output, test result, or freshly fetched docs URL) or be explicitly demoted to `Unknown` with a reason (`~/CLAUDE.md` §2.1 External Truth / §2.3 Completion). The earlier `evidence_anchor.py` hook re-prompted per turn and was removed as noise.
- **Durable-learning capture** — as the last step of any substantive turn, the agent self-vets whether it produced a durable, verified, reusable insight and, if so, persists it inline with `,ai-kb remember` (`~/CLAUDE.md` §4.1, mirrored in `~/AGENTS.md` / `~/.gemini/GEMINI.md`). This replaces the earlier `learning_reminder.py` `stop` hook, whose auto-submitted "persist learnings" prompt was both intrusive and capped at once per conversation. The SOP habit has no per-session cap and never injects a fake user turn.

At session start, interactive harnesses inject the verification-discipline prefix from [`prefix.txt`](../../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt).

| Consumer                                 | How it gets `prefix.txt`                                                                |
| ---------------------------------------- | --------------------------------------------------------------------------------------- |
| Cursor/Claude/Codex-style hook harnesses | `session_context.py` reads it at runtime                                                |
| Copilot                                  | `agent-memory` SDK extension calls `session_context.py` and returns `additionalContext` |
| Pi                                       | `ai-kb-recall.ts` injects it at first `before_agent_start`                              |
| Custom subagents                         | profile templates render it as the first body/developer-instructions block              |
| tmux manual prompt wrap                  | `Alt-Enter` pastes the same text; see [Tool configs](../tool-configs/index.md)          |

`cursor-agent` has no per-prompt context-injection hook; `beforeSubmitPrompt` is allow/block only. Pi could inject the prefix per turn but intentionally does not, avoiding repeated fixed text.

Resident FastEmbed warm-up is independently opt-in; it is not implied by calling `session_context.py`:

| Consumer             | Warm-up path                                                                                |
| -------------------- | ------------------------------------------------------------------------------------------- |
| Claude and Gemini    | Session-start command sets `AI_EMBED_WARM=1`                                                |
| OpenCode and Copilot | Session-start payload sets `warm_embedder: true`                                            |
| Pi                   | Its TypeScript extension calls `~/lib/,ai-kb/embed_client.py ensure` during `session_start` |
| Cursor and Codex     | No warm-up because they have no automatic per-turn retrieval path                           |

`session_context.py` runs a requested `ensure` with a four-second bound and discards failures, except that `AI_AGENT_DEPTH=fast` suppresses warm-up because that profile disables per-turn retrieval. Shared `perturn_recall.py` sets `AI_EMBED_CONNECT_ONLY=1` for its `,ai-kb search`; Pi applies the same environment contract to its hybrid searches. Per-turn code therefore never starts or replaces a worker. The generation-specific worker is served from `~/lib/,ai-kb/`, exits after 300 inactive seconds, and fails open by omitting the recall block if it is absent or invalid. Default/manual CLI, Ralph, `remember`, and `reembed` calls retain the one-shot `embed_runner.py` path. See [Cross-agent memory](cross-agent-memory.md) for the exact `fast`/`balanced`/`deep` budgets and fixture provenance.

Runtime state is intentionally outside chezmoi and outside worktrees:

```text
/tmp/specs/<workspace-path-without-leading-slash>/_active_topic.txt
/tmp/specs/<workspace-path-without-leading-slash>/.session-topic-<session-id>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.worklog.jsonl
/tmp/specs/<workspace-path-without-leading-slash>/.recall-seen-<session-key>.json
/tmp/specs/<workspace-path-without-leading-slash>/.worklog-queue-v1/<session-key>/
/tmp/specs/<workspace-path-without-leading-slash>/.worklog-locks-v1/
```

`worklog_dispatcher.sh` is shell glue only: it validates the recorder, captures the JSON payload, starts `worklog_recorder.py` in the background, and closes the adapter-facing path. The Python queue module owns the state machine:

- each canonical session (`conversation_id`, then `session_id`, then `generation_id`, else topic fallback) receives atomically published, fsynced sequence files;
- stable `worklog_id`, `session_key`, and `worklog_seq` fields make crash replay idempotent and preserve per-session order;
- a shared/exclusive spec activity lock linearizes complete harvests against new enqueues while preserving cross-session enqueue concurrency;
- a per-target lock plus timestamp ordering keeps shared-topic logs chronological enough for harvest;
- pending state is capped at 256 events and 1 MiB per session; worklogs retain 200 complete JSONL records;
- the transient flusher exits after 80ms idle or two seconds total, and drained queue/error directories age out after seven days;
- queue-full, invalid-record, spawn, and flush failures remain in bounded error ledgers. Session startup warns, and `,ai-kb harvest` exits nonzero, while the agent-facing tool path remains fail-open.

The worklog is not only startup context — it is harvestable. `,ai-kb harvest --session-id <id>` first flushes all pending session queues, fails visibly if pending/error state remains, then resolves that session's binding through `agent_memory.py`, reads its `<topic>.worklog.jsonl`, and surfaces durable-memory candidates (failing-then-fixed commands, recurring errors, repeated commands) as prefilled `,ai-kb remember` lines. It is a manual, read-only aid that never writes capsules and never re-prompts the agent, so it stays inside the same no-`stop`-hook discipline described above. See [AI knowledge base](ai-kb.md#worklog-harvest).

BM25 capsule warm-start and per-turn recall share `.recall-seen-<session-key>.json`, keyed by the canonical payload identity (`conversation_id`, then `session_id`, then `generation_id`). This capsule warm-start is separate from resident embedder warm-up. Pi uses the canonical key returned by `,agent-memory status`, preserving dedupe when its extension reloads or a session resumes.

Bounded-context rules:

| Rule                                                     | Why                                                           |
| -------------------------------------------------------- | ------------------------------------------------------------- |
| Oversized specs are omitted with a pointer               | Avoid slicing partial memory into the prompt                  |
| Only whole recent worklog entries are included           | Avoid half-events that mislead the agent                      |
| Worklog JSONL files trim during serialized queue flush   | Keep startup injection bounded without concurrent lost writes |
| Session bindings are per agent session                   | Let parallel sessions join the same bucket or separate safely |
| Topic buckets are listed before full context is injected | Prevent unrelated `main` sessions inheriting stale memory     |
| Feature/topic worktrees keep `current` continuity        | Preserve useful project continuity in isolated worktrees      |
| Review topics run clean-room by default                  | Reduce bias in re-reviews                                     |

`session_context.py`'s `sessionStart` injection and `,agent-memory select`'s printed context are two independent clean-room entrypoints that apply the same rules: text exceeding the character bound is never truncated — it is omitted wholesale and replaced with a pointer to the spec file — and review topics (topic starts with `review`, or the spec's first `target:` line names a `PR`) have prior `verified facts`/`findings`/`verdict`/etc. sections and the worklog tail stripped **before** that bound is checked, so a sanitized-but-still-oversized review body is also omitted with a pointer rather than injected verbatim. `scripts/agent_memory.py` cannot import `session_context.py` directly — it always runs from the chezmoi source tree via the `,agent-memory` launcher, while `session_context.py` is deployed standalone to `~/.agents/hooks/` and only imports its sibling `hook_common.py` — so the clean-room predicate/renderer (`is_review_topic`, `neutral_review_spec`, `bounded_or_omitted`, the size bound) is mirrored in both files with an explicit "change both together" comment rather than shared through a single import.

On shared branches (`main`, `master`, `dev`, `develop`, `trunk`) without a session binding, `session_context.py` injects `### Topic Buckets`. The agent should bind automatically when one bucket clearly matches, create a new bucket when none matches, and ask only when multiple buckets plausibly match. `,agent-memory select` prints the selected spec/worklog context immediately (clean-room-sanitized, same as above) and binds later session-start hooks to the same topic. Topic buckets are listed newest-first by the most recent spec/worklog update. Each entry includes a short summary pulled from `summary:` (preferred) or `target:`/`action:` lines in the topic spec so the list is scannable at a glance. Add a `summary: <one-line label>` to the topic spec to persist a concise description alongside the topic name.

Force a clean session with either:

```bash
AGENT_HOOK_CONTEXT=0
```

or by placing `_no_session_context` / `<topic>.no_context` under the workspace's `/tmp/specs/...` directory.

The user-facing control plane is `,agent-memory`:

- `,agent-memory status [--session-id <id>]` — show the selected topic, including a session-bound bucket when a session id is given.
- `,agent-memory select <topic> --session-id <id>` — bind one agent session to an existing topic bucket.
- `,agent-memory select <topic> --create --session-id <id>` — seed a new topic bucket and bind only this session to it.
- `,agent-memory use <topic>` — set the legacy workspace-level pointer used by the CLI control plane; shared-branch session-start context still uses `select` session bindings.
- `,agent-memory wipe-current [--session-id <id>]` — delete the selected topic's spec, worklog, and no-context sentinel.

`status --json` also emits the sanitized `session_key` that adapters use for binding and recall-state filenames.

Sources:

- [`home/exact_bin/executable_,agent-memory`](../../../../home/exact_bin/executable_,agent-memory)
- [`scripts/agent_memory.py`](../../../../scripts/agent_memory.py)
- [`home/dot_config/fish/completions/readonly_,agent-memory.fish`](../../../../home/dot_config/fish/completions/readonly_,agent-memory.fish)

`select` is the normal agent-facing path for session continuity; it writes `.session-topic-<session-id>.txt` and never changes another live session's bucket. `use <topic>` rejects the generic `current` and manages only the workspace-level default/suggestion path. On default branches without an explicit active topic or session binding, `wipe-current` targets the latest `session-*` topic.

Claude Code mirrors the shared subset through `settings.personal.json` and `settings.work.json`: session context plus depth-controlled resident warm-up, asynchronous tool worklog recording, and depth-controlled per-turn AI-KB recall (`UserPromptSubmit` → `perturn_recall.py`; see [Cross-agent memory](cross-agent-memory.md)). The local llama.cpp settings file is intentionally excluded. Copilot uses `~/.copilot/extensions/agent-memory/extension.mjs` for the same shared scripts — session context (`onSessionStart` → `session_context.py`), per-turn AI-KB recall (`onUserPromptSubmitted` → `perturn_recall.py`), and asynchronous tool worklog dispatch (`onPostToolUse*` → `worklog_dispatcher.sh`) — because JSON command hooks run but do not ingest `SessionStart` context output. Pi applies the same depth profile during `session_start` and `before_agent_start`.

Verification:

```bash
python3 scripts/tests/test_agent_hooks.py
python3 -m unittest discover -s scripts -t scripts -k test_recall_worklog
node --test scripts/tests/copilot_agent_memory_extension.test.mjs
python3 scripts/test_embed.py
python3 -m unittest discover -s scripts -t scripts -k test_agent_memory
chezmoi diff --no-pager
chezmoi apply --force --no-tty
,agent-memory status --session-id <id>
```
