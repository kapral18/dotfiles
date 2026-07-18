---
sidebar_position: 1
title: Hook memory
---

# Hook memory (`/tmp/specs`, `,agent-memory`)

Agent sessions are ephemeral; the work they do is not. Hook memory is the layer that gives every interactive harness (Cursor, Claude, Codex, OpenCode, Copilot, Pi) the same three session-scoped memory behaviors without any harness-specific logic in the memory system itself:

1. **Session-start context injection** — a new session receives the verification-discipline prefix, the active topic's spec, and a recent worklog tail, so it resumes where the last session left off.
2. **Worklog recording** — every tool call is appended to a crash-safe, per-topic JSONL trail as the session works.
3. **Topic buckets** — sessions bind to a named topic under `/tmp/specs`, so parallel sessions can share one work thread or stay isolated.

The moving parts:

| Piece                                                                                             | Role                                                                                |
| ------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| [`session_context.py`](../../../../home/exact_dot_agents/exact_hooks/)                            | Session-start hook: injects prefix, topic index, spec, worklog tail                 |
| [`worklog_dispatcher.sh`](../../../../home/exact_dot_agents/exact_hooks/) → `worklog_recorder.py` | Post-tool hook: records tool events off the critical path                           |
| [`perturn_recall.py`](../../../../home/exact_dot_agents/exact_hooks/) + `correction_detector.py`  | Per-prompt hook: AI-KB recall plus precision-first user-correction directive        |
| `/tmp/specs/<workspace>/`                                                                         | Runtime state: topic specs, worklogs, bindings (outside chezmoi, outside worktrees) |
| [`,agent-memory`](../../workflow/custom-commands/catalog.md)                                      | User/agent-facing control plane over topics and bindings                            |
| [`scripts/spec_mirror.py`](../../../../scripts/spec_mirror.py)                                    | Reboot survival: mirrors named topics to `~/.local/state/agent-specs/`              |

Shared hook scripts deploy from [`home/exact_dot_agents/exact_hooks/`](../../../../home/exact_dot_agents/exact_hooks/) to `~/.agents/hooks/`. Each harness wires the same scripts through its own adapter — see [Per-harness wiring](#per-harness-wiring).

## Using it

### Topic buckets

On shared branches (`main`, `master`, `dev`, `develop`, `trunk`) with no session binding, session start injects a `### Topic Buckets` index instead of full context. The agent binds automatically when exactly one bucket matches the request, creates a new bucket when none matches, and asks only when several plausibly match.

Buckets are listed newest-first by most recent spec/worklog update. Each entry carries a one-line summary pulled from the spec's `summary:` (preferred) or `target:`/`action:` lines — add a `summary: <one-line label>` to a topic spec to make the list scannable.

Feature/topic worktrees keep `current` continuity instead, so isolated worktrees retain their own project thread.

### The `,agent-memory` control plane

- `,agent-memory status [--session-id <id>]` — show the selected topic, including the session-bound bucket when a session id is given. `--json` also emits the sanitized `session_key` adapters use for binding and recall-state filenames.
- `,agent-memory select <topic> --session-id <id>` — bind one agent session to an existing bucket by writing `.session-topic-<session-id>.txt`. Pre-bind events from the session's `session-*` fallback worklog are flushed and folded into `<topic>.worklog.jsonl`, so the trail is not split. `select` prints the topic's spec/worklog context immediately (clean-room-sanitized, see below) and binds later session-start hooks to the same topic. It never changes another live session's bucket.
- `,agent-memory select <topic> --create --session-id <id>` — seed a new bucket and bind only this session to it.
- `,agent-memory note <kind> "<text>" [--ref <anchor>]` — record a structured insight into the bound topic's worklog through the crash-safe queue. Kinds are the `,ai-kb` capsule kinds (minus `doc`) plus task-scoped `question` and `decision`; non-question notes surface later as `,ai-kb harvest` candidates with their kind kept verbatim (`decision` maps to a `fact` candidate).
- `,agent-memory merge <source-topic> <dest-topic> [--dry-run]` — fold a duplicate topic into a named destination: flushes pending queues first, merges worklogs by `ts` under the 200-line cap, rewrites session bindings plus `_active_topic.txt`, and deletes the source `.no_context` sentinel rather than propagating it (so context is not silently suppressed).
- `,agent-memory use <topic>` — set the legacy workspace-level pointer used by the CLI control plane. It rejects the generic `current`; shared-branch session-start context still uses `select` session bindings.
- `,agent-memory wipe-current [--session-id <id>]` — delete the selected topic's spec, worklog, and no-context sentinel. On default branches without an explicit topic or binding, it targets the latest `session-*` topic.

### Harvesting the worklog

The worklog is not just startup context — `,ai-kb harvest --session-id <id>` mines it for durable-memory candidates: structured `note` events, failing-then-fixed commands, recurring errors, and repeated commands become prefilled `,ai-kb remember` lines. Harvest first flushes all pending session queues and fails visibly if pending/error state remains. It is a manual, read-only aid: it never writes capsules and never re-prompts the agent. See [AI knowledge base](ai-kb.md#worklog-harvest).

Per-turn correction detection is a prompt-only helper for that write path. `correction_detector.py` uses narrow conduct-shaped patterns such as unrequested action, omission correction, unverified claim, guessed-not-tested, and repeat failure. When it fires, `perturn_recall.py` injects a same-turn directive to record `,agent-memory note anti_pattern` when the correction is genuine, and to promote it with `,ai-kb remember` only after the lesson is verified and durable. The detector is fail-open and does not write memory itself.

### Forcing a clean session

Set `AGENT_HOOK_CONTEXT=0`, or place `_no_session_context` (workspace-wide) or `<topic>.no_context` (per topic) under the workspace's `/tmp/specs/...` directory.

## Per-harness wiring

All harnesses call the same three shared scripts; only the adapter differs.

| Harness     | Adapter                                                                                  | Session start                                                                                                                               | Per prompt                                                          | Post tool                                                                                                               |
| ----------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Cursor      | [`hooks.json`](../../../../home/dot_cursor/hooks.json) → `~/.cursor/hooks.json`          | `sessionStart` → `AI_EMBED_WARM=1 session_context.py`                                                                                       | `beforeSubmitPrompt` → `perturn_recall.py`                          | `afterShellExecution`, `postToolUse`, `postToolUseFailure`, `afterFileEdit` → `worklog_dispatcher.sh`                   |
| Claude Code | `settings.personal.json` / `settings.work.json`                                          | `session_context.py` with depth-controlled warm-up                                                                                          | `UserPromptSubmit` → `perturn_recall.py`                            | async worklog recording                                                                                                 |
| Codex       | [`hooks.json.tmpl`](../../../../home/dot_codex/hooks.json.tmpl)                          | `SessionStart` → `session_context.py` (`AI_EMBED_WARM=1` via `/bin/sh -c`)                                                                  | `UserPromptSubmit` → `perturn_recall.py`                            | `PostToolUse` → `worklog_dispatcher.sh`                                                                                 |
| OpenCode    | [`agent-memory.ts`](../../../../home/dot_config/opencode/plugins/agent-memory.ts) plugin | `experimental.chat.system.transform` fetches `session_context.py` once (`warm_embedder: true`) and appends to every request's system prompt | third plugin hook (see [Cross-agent memory](cross-agent-memory.md)) | `tool.execute.after` → `worklog_dispatcher.sh` with a synthesized `PostToolUse` payload carrying OpenCode's `sessionID` |
| Copilot     | `~/.copilot/extensions/agent-memory/extension.mjs` (SDK extension)                       | `onSessionStart` → `session_context.py`, returned as `additionalContext`                                                                    | `onUserPromptSubmitted` → `perturn_recall.py`                       | `onPostToolUse*` → `worklog_dispatcher.sh`                                                                              |
| Pi          | `ai-kb-recall.ts` extension                                                              | prefix at first `before_agent_start`; depth profile at `session_start`                                                                      | hybrid recall (see [Cross-agent memory](cross-agent-memory.md))     | forwards `tool_result` as a Copilot-shaped `postToolUse*` payload                                                       |

Harness-specific notes:

- **Cursor gained a per-prompt context-injection channel in `2026.07.16`**: the installed bundle's `HOOK_STEPS_SUPPORTING_ADDITIONAL_CONTEXT` covers `sessionStart`, `beforeSubmitPrompt`, and the tool hooks, with a 10,000-char carrier cap (older `2026.07.09` read `beforeSubmitPrompt` output as allow/block only). The event payload carries `prompt`, `workspace_roots`, `session_id`/`conversation_id`, and `hook_event_name`, and hook commands run through a shell heredoc, so the env-prefixed commands and the shared hooks work unmodified. Cursor consumes the top-level snake `additional_context` key (its `hookSpecificOutput` fallback expects the Claude-style event name rather than the echoed cursor-native one), so `perturn_recall.py` emits both channels like `session_context.py`. With `AI_EMBED_WARM=1` on `sessionStart`, cursor sessions get real per-turn recall and no longer receive the `### Recall Notice` fallback; the notice still keys off the warm-up signal for any adapter that sends neither `AI_EMBED_WARM=1` nor `warm_embedder: true`.
- **Codex executes hook commands without a shell**: a literal `$HOME/...` never expands and the hook fails with `hook: <name> Failed`. The adapter is a chezmoi template that renders absolute paths; env for the warm-up and for the per-turn output strip is set through explicit `/bin/sh -c` wrappers. Codex also strictly validates hook results and rejects unknown top-level keys, so both wrappers set `AGENT_HOOK_OUTPUT=hook_specific`, which makes the shared `emit()` keep only the `hookSpecificOutput` channel (the top-level `additional_context` key is the channel Cursor consumes). Payload shapes are Claude-compatible (verified against codex 0.144.4): `SessionStart` and `UserPromptSubmit` carry `session_id`, `cwd`, and `prompt`, and `hookSpecificOutput.additionalContext` from `UserPromptSubmit` lands in the transcript as a developer message. `codex exec` dispatches `SessionStart`, `UserPromptSubmit`, and `PostToolUse` like interactive sessions.
- **Codex trust**: changing `hooks.json` invalidates the `[hooks.state]` trusted hashes codex appends to `config.toml`. After deploying a hook change, run an interactive codex session and re-trust via `/hooks` (or `--dangerously-bypass-hook-trust` for one-off exec runs).
- **Copilot** uses the SDK extension because its JSON command hooks run but do not ingest `SessionStart` stdout as context. The extension translates Copilot's camelCase SDK payloads to the shared snake_case script contract.
- **Copilot sub-agents** set `COPILOT_AGENT_SESSION_ID` to the parent session id. Worklog writes and the `,agent-memory` CLI (`status`/`note`) use that env value to inherit the parent's selected topic bucket, or the parent's session fallback bucket, so explicit agent commands land where the write path writes; hook startup/read/inject paths ignore it so blind lanes receive no parent context. Non-Copilot harnesses are unaffected.
- **OpenCode** omits `duration` and `status` — the plugin API does not expose them.
- **Pi** could inject the prefix per turn but intentionally does not, avoiding repeated fixed text.
- **Claude Code** intentionally excludes the local llama.cpp settings file from this wiring.

Session-start prefix injection (`prefix.txt`) reaches every consumer the same way:

| Consumer                                 | How it gets [`prefix.txt`](../../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt) |
| ---------------------------------------- | ------------------------------------------------------------------------------------------- |
| Cursor/Claude/Codex-style hook harnesses | `session_context.py` reads it at runtime                                                    |
| Copilot                                  | `agent-memory` SDK extension returns it as `additionalContext`                              |
| Pi                                       | `ai-kb-recall.ts` injects it at first `before_agent_start`                                  |
| Custom subagents                         | profile templates render it as the first body/developer-instructions block                  |
| tmux manual prompt wrap                  | `Alt-Enter` pastes the same text; see [Tool configs](../tool-configs/index.md)              |

### Embedder warm-up

Resident FastEmbed warm-up is independently opt-in per adapter; calling `session_context.py` does not imply it:

| Consumer                          | Warm-up path                                                                                |
| --------------------------------- | ------------------------------------------------------------------------------------------- |
| Claude, Gemini, Codex, and Cursor | Session-start command sets `AI_EMBED_WARM=1`                                                |
| OpenCode and Copilot              | Session-start payload sets `warm_embedder: true`                                            |
| Pi                                | Its TypeScript extension calls `~/lib/,ai-kb/embed_client.py ensure` during `session_start` |

`session_context.py` runs a requested `ensure` with a four-second bound and discards failures; `AI_AGENT_DEPTH=fast` suppresses warm-up because that profile disables per-turn retrieval. `perturn_recall.py` sets `AI_EMBED_CONNECT_ONLY=1` for its `,ai-kb search`, and Pi applies the same environment contract to its hybrid searches — per-turn code never starts or replaces a worker. `AI_KB_RECALL_TIMEOUT` can raise (never shrink) the per-profile search timeout for slow or loaded environments such as full-suite test runs. The generation-specific worker is served from `~/lib/,ai-kb/`, exits after 300 idle seconds, and fails open by omitting the recall block when absent or invalid. Default/manual CLI, `remember`, and `reembed` calls retain the one-shot `embed_runner.py` path. See [Cross-agent memory](cross-agent-memory.md) for the `fast`/`balanced`/`deep` budgets and fixture provenance.

## Design rules

**Hooks observe and inject context; they never re-prompt the agent.** No hook runs on `stop`. Two disciplines are deliberately enforced by SOP instruction instead of hooks:

- **Evidence anchoring** — a factual/runtime claim must carry a hard source anchor or be demoted to `Unknown` with a reason (`~/CLAUDE.md` §2.1 External Truth / §2.3 Completion).
- **Durable-learning capture** — at the end of any substantive turn the agent self-vets for a durable, verified, reusable insight and persists it inline with `,ai-kb remember` (`~/CLAUDE.md` §4.1, mirrored in `~/AGENTS.md` / `~/.gemini/GEMINI.md`). The SOP habit has no per-session cap and never injects a fake user turn.

**Injected context is bounded, whole, and clean-room:**

| Rule                                                     | Why                                                           |
| -------------------------------------------------------- | ------------------------------------------------------------- |
| Oversized specs are omitted with a pointer               | Avoid slicing partial memory into the prompt                  |
| Only whole recent worklog entries are included           | Avoid half-events that mislead the agent                      |
| Worklog JSONL files trim during serialized queue flush   | Keep startup injection bounded without concurrent lost writes |
| Session bindings are per agent session                   | Let parallel sessions join the same bucket or separate safely |
| Topic buckets are listed before full context is injected | Prevent unrelated `main` sessions inheriting stale memory     |
| Feature/topic worktrees keep `current` continuity        | Preserve useful project continuity in isolated worktrees      |
| Review topics run clean-room by default                  | Reduce bias in re-reviews                                     |

Text exceeding the character bound is never truncated — it is omitted wholesale and replaced with a pointer to the spec file. Review topics (topic name starts with `review`, or the spec's first `target:` line names a PR) additionally have prior `verified facts`/`findings`/`verdict` sections and the worklog tail stripped **before** the bound is checked, so a sanitized-but-still-oversized review body is also omitted rather than injected verbatim.

## Internals (for maintainers)

### Runtime state layout

Runtime state lives outside chezmoi and outside worktrees:

```text
/tmp/specs/<workspace-path-without-leading-slash>/_active_topic.txt
/tmp/specs/<workspace-path-without-leading-slash>/.session-topic-<session-id>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.worklog.jsonl
/tmp/specs/<workspace-path-without-leading-slash>/.recall-seen-<session-key>.json
/tmp/specs/<workspace-path-without-leading-slash>/.worklog-queue-v1/<session-key>/
/tmp/specs/<workspace-path-without-leading-slash>/.worklog-locks-v1/
```

### Worklog queue

`worklog_dispatcher.sh` is shell glue only: it validates the recorder, captures the JSON payload, starts `worklog_recorder.py` in the background, and returns without waiting for worklog I/O. The Python queue module owns the state machine:

- each canonical session (`conversation_id`, then `session_id`, then `generation_id`, else topic fallback) receives atomically published, fsynced sequence files;
- stable `worklog_id`, `session_key`, and `worklog_seq` fields make crash replay idempotent and preserve per-session order;
- a shared/exclusive spec activity lock linearizes complete harvests against new enqueues while preserving cross-session enqueue concurrency;
- a per-target lock plus timestamp ordering keeps shared-topic logs chronological enough for harvest;
- pending state is capped at 256 events and 1 MiB per session; worklogs retain 200 complete JSONL records;
- Copilot sub-agent tool-call ids (`toolu_*` / `call_*`) route through the parent session key on the write path only when `COPILOT_AGENT_SESSION_ID` is present;
- the transient flusher exits after 80 ms idle or two seconds total, and drained queue/error directories age out after seven days;
- the same seven-day age gate sweeps stale per-session fallback state after each flush pass: `session-*` fallback worklogs and `.recall-seen-*` dedupe files older than the gate are removed (named-topic worklogs are never candidates);
- queue-full, invalid-record, spawn, and flush failures remain in bounded error ledgers. Session startup warns and `,ai-kb harvest` exits nonzero, while the agent-facing tool path stays fail-open.

### Recall-state dedupe

BM25 capsule warm-start and per-turn recall share `.recall-seen-<session-key>.json`, keyed by the canonical payload identity (`conversation_id`, then `session_id`, then `generation_id`). Capsule warm-start is separate from resident embedder warm-up. Pi uses the canonical key returned by `,agent-memory status`, preserving dedupe when its extension reloads or a session resumes.

### Duplicated clean-room logic

`session_context.py`'s `sessionStart` injection and `,agent-memory select`'s printed context are two independent entrypoints that apply the same clean-room rules. `scripts/agent_memory.py` cannot import `session_context.py`: `agent_memory.py` always runs from the chezmoi source tree via the `,agent-memory` launcher, while `session_context.py` is deployed standalone to `~/.agents/hooks/` and imports only its sibling `hook_common.py`. The clean-room predicate/renderer (`is_review_topic`, `neutral_review_spec`, `bounded_or_omitted`, the size bound) is therefore mirrored in both files with an explicit "change both together" comment.

### Reboot survival

[`scripts/spec_mirror.py`](../../../../scripts/spec_mirror.py) (deployed beside the hooks and `,agent-memory`) mirrors named-topic files and the `_active_topic.txt` pointer to `~/.local/state/agent-specs/` at session start and on `,agent-memory` checkpoints, and restores only missing files when `/tmp/specs` was wiped. `wipe-current` and `merge` forget the mirror copies of removed topics; `current` and `session-*` buckets are never mirrored.

## Sources and verification

- [`home/exact_bin/executable_,agent-memory`](../../../../home/exact_bin/executable_,agent-memory)
- [`scripts/agent_memory.py`](../../../../scripts/agent_memory.py)
- [`home/dot_config/fish/completions/readonly_,agent-memory.fish`](../../../../home/dot_config/fish/completions/readonly_,agent-memory.fish)

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
