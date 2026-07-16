# Agent Hooks

Shared lifecycle hooks for terminal AI agents.

Cursor CLI is the primary runtime. Claude Code, Codex, Gemini, OpenCode, and Copilot reuse compatible shared scripts.
Those scripts cover session context, resident-embedder warm-up and per-turn recall where supported, and worklog recording.
Each adapter passes its native session ID so topic selection, worklogs, and recall dedupe use the same binding.
PR review anchor verification is instruction-owned by the review/GitHub skills, not enforced by a shell hook.
Pi does not use this `hooks.json`-style lifecycle; it has its own TypeScript extension API.
Pi's durable-memory recall therefore lives in a pi extension (`home/dot_pi/agent/extensions/ai-kb-recall.ts`) rather than here.
That extension reuses the same `/tmp/specs` topic resolution (via `,agent-memory status --json --session-id <id>`) and the same `,ai-kb` retrieval, and forwards `tool_result` events to `worklog_dispatcher.sh` so pi sessions feed the shared worklog trail.
This keeps behavior consistent across runtimes — see the AI knowledge base doc for the cross-runtime retrieval table.

Runtime state is kept outside chezmoi and outside worktrees:

```text
/tmp/specs/<workspace-path-without-leading-slash>/_active_topic.txt
/tmp/specs/<workspace-path-without-leading-slash>/.session-topic-<session-id>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.worklog.jsonl
/tmp/specs/<workspace-path-without-leading-slash>/.recall-seen-<session-key>.json
/tmp/specs/<workspace-path-without-leading-slash>/.worklog-queue-v1/<session-key>/
/tmp/specs/<workspace-path-without-leading-slash>/.worklog-locks-v1/
```

`/tmp/specs` stays the primary, best-effort store, but named topics no longer die with a reboot:
`spec_mirror.py` copies each named topic's spec, worklog, sentinel, and the `_active_topic.txt` pointer to a persistent per-workspace mirror (`~/.local/state/agent-specs/`, override via `AGENT_MEMORY_MIRROR_ROOT`).
Sync happens at deliberate checkpoints — session start and `,agent-memory` status/select/use/note/merge —
never on the per-tool-event hot path.
When `/tmp/specs` is wiped, session start and `,agent-memory` restore only the missing named-topic files (live `/tmp` state always wins), while `wipe-current` and `merge` also forget the mirror copies so a deleted topic cannot resurrect.
`current` and `session-*` fallback buckets are intentionally never mirrored.

Session-scoped topic bindings live in `.session-topic-<session-id>.txt`.
They select which shared topic bucket this one agent session loads, without changing any other live session.
`_active_topic.txt` is a workspace-level default/suggested bucket hint, not permission to inject that topic into every new session.

Default-branch workspaces are treated as shared scratch space.
If the current git branch is `main`, `master`, `dev`, `develop`, or `trunk` and no session binding exists, hook state uses a session-scoped fallback topic (`session-<id>`).
Instead of loading another session's active topic, `session_context.py` injects a bounded `### Topic Buckets` index.
The list is sorted newest-first by the most recent spec/worklog update and shows a short summary derived from `summary:` (preferred) or `target:`/`action:` lines in the topic spec.
Add `summary: <one-line label>` to persist a concise description alongside the topic name.
The agent should bind automatically when exactly one bucket clearly matches the user's request, create a new bucket when none matches, and ask one question only when multiple buckets plausibly match.
It then runs `,agent-memory select <topic> --session-id <id>` or `,agent-memory select <new-topic> --create --session-id <id>` itself.
Feature/topic worktrees keep `current` continuity by default when no `_active_topic.txt` hint is present.

For a session-bound named topic with a non-empty `<topic>.txt` spec, `session_context.py` injects the full spec/worklog context and a relevance-gated `### Relevant Learnings (,ai-kb)` block.
A session-bound named topic is neither `current` nor a `session-*` fallback.
The hook runs `,ai-kb search` with the spec text as the query (`bm25` lane, no embedder, bounded by the hook timeout).
It surfaces up to three capsules via `--workspace-gate`, which makes the KB itself keep only capsules local to this workspace or scoped `domain`/`universal`, so durable memory seeds the session automatically.
Unbound, ad-hoc/`session-*`, and review topics get no capsule warm-start.
This is the only automatic session-start capsule retrieval; supported runtimes also perform per-turn recall.
Cursor cannot inject context per-turn (`beforeSubmitPrompt` carries no context-injection output), so mid-task relevance comes from the agent's own `,ai-kb search` calls against its actual task.
The hook reads the KB but never writes it; persistence stays agent-driven.
Warm-start and per-turn recall persist injected capsule IDs in `.recall-seen-<session-key>.json`.
The canonical session key follows `conversation_id`, then `session_id`, then `generation_id`;
Pi persists the same state across extension reloads and session resumes.

Resident FastEmbed warm-up is a separate, explicit lifecycle for automatic per-turn consumers:

- Claude, Gemini, and Codex set `AI_EMBED_WARM=1` on their session-start command.
- OpenCode and Copilot pass `warm_embedder: true` in their session-start payload.
- Pi calls `~/lib/,ai-kb/embed_client.py ensure` from its TypeScript `session_start` handler.
- Cursor does not warm the resident because it has no per-turn retrieval wiring;
  its session context therefore carries a `### Recall Notice` directing the agent to run `,ai-kb search` itself mid-task and to capture insights with `,agent-memory note`.

`AI_AGENT_DEPTH` applies one recall contract to Claude, Gemini, OpenCode, Copilot, Codex, and Pi:

| Depth      | Startup BM25 | Resident warm-up | Per-turn fetch / inject | Prompt / body caps | Timeout |
| ---------- | ------------ | ---------------- | ----------------------- | ------------------ | ------- |
| `fast`     | unchanged    | skipped          | disabled                | n/a                | n/a     |
| `balanced` | unchanged    | requested        | 6 / 3                   | 600 / 240 chars    | 6s      |
| `deep`     | unchanged    | requested        | 12 / 5                  | 1200 / 360 chars   | 9s      |

Unset, empty, or invalid values resolve to `balanced`, which is the prior behavior.
Every enabled profile keeps the existing `hybrid` mode, `0.55` top-cosine gate, `0.85` tail floor, the KB-owned `--workspace-gate` scope gate, session dedupe, stdin-only query transport, and connect-only resident contract.

Requested warm-up is bounded and fail-open.
Shared `perturn_recall.py` and Pi's hybrid query path set `AI_EMBED_CONNECT_ONLY=1`;
the current-turn hot path never spawns, restarts, evicts, or replaces a worker.
A missing or invalid worker yields no recall block and does not interrupt the request.
Default/manual `,ai-kb`, `remember`, and `reembed` remain on the one-shot `embed_runner.py` path.

The deployed `~/lib/,ai-kb/embed_client.py` selects a generation-specific Unix socket from protocol version, complete worker source, model, and expected dimension.
Warm-up resolves the configured model dimension; connect-only callers discover the matching ready generation without spawning.
Its user-owned runtime root is `0700`, the socket and start lock are `0600`, startup markers are atomically published and tied to the expected worker command, resident socket messages are bounded, and the worker never logs or echoes their prompt text.
One default BGE-small worker measured about 320 MiB RSS; two coexisting deployment generations measured about 625 MiB total.
The worker exits after 300 inactive seconds while removing only its own socket inode.

Session-start context is bounded without injecting partial memory.
An oversized active topic spec is omitted with a pointer to the full file instead of being sliced into the prompt.
Only whole recent worklog entries are included. Worklogs are trimmed during serialized queue flush so runtime state does not grow forever.
The same flush pass also removes `session-*` fallback worklogs and `.recall-seen-*` dedupe files older than seven days;
named-topic worklogs are never swept.

Tool adapters invoke `worklog_dispatcher.sh`, which captures the JSON payload and launches `worklog_recorder.py` without waiting for filesystem bookkeeping.
The recorder durably enqueues a session-sequenced event, and a transient worker flushes it under a per-target lock.
Queue records are atomically published and fsynced; stable IDs make crash replay idempotent, and target output is timestamp-ordered for harvest.
Pending state is capped at 256 events and 1 MiB per session, output at 200 records, worker lifetime at 80ms idle/two seconds total, and drained queue/error directories at seven days.
Failures stay in bounded error ledgers: agents fail open, session startup warns, and `,ai-kb harvest` refuses to report success while pending/error state remains.

Review topics run in clean-room mode by default.
When the active topic name starts with `review` or the spec targets a PR, startup context keeps neutral metadata such as target, state, diff, and files.
It omits prior `verified facts`, `findings`, `verdict`, inline comments, and recent worklog tails.
Read the spec manually only when you intentionally want prior-session conclusions.

To start a clean session with no injected topic/worklog context, use one of:

```bash
AGENT_HOOK_CONTEXT=0 cursor-agent
touch /tmp/specs/<workspace-path-without-leading-slash>/_no_session_context
touch /tmp/specs/<workspace-path-without-leading-slash>/<topic>.no_context
```

The sentinel files are intentionally outside the worktree. Remove them to restore session context injection.

Use `,agent-memory` to set the active topic or as a dead switch for persisted hook memory:

```bash
,agent-memory status --session-id <id>
,agent-memory select <topic> --session-id <id>
,agent-memory select <new-topic> --create --session-id <id>
,agent-memory use <topic>
,agent-memory merge <source-topic> <dest-topic> [--dry-run]
,agent-memory note <fact|gotcha|pattern|anti_pattern|recipe|principle|question> "<text>" [--ref <anchor>]
,agent-memory wipe-current
,agent-memory wipe-current --dry-run
,agent-memory wipe-current --reset-active
```

`select` binds one agent session to a topic bucket by writing `.session-topic-<session-id>.txt`.
It seeds `<topic>.txt` only with `--create`.
At bind time it also flushes the session's pending queue and folds the session's pre-bind `session-*` fallback worklog into `<topic>.worklog.jsonl`, so the trail is not split across buckets.
`use` manages the workspace-level default/suggested bucket: it writes `_active_topic.txt` and seeds `<topic>.txt` (rejecting the generic `current`).
Use it only when you intentionally want to mark a default/suggested bucket for the workspace.
`note` is the deliberate mid-task capture surface for insights that leave no failing command behind:
it records a structured event (`note_kind`, text, refs) through the same crash-safe queue as tool worklogs.
Note kinds are the `,ai-kb` capsule kinds (minus ingestion-only `doc`) plus task-scoped `question` —
one vocabulary, so a model never translates between capture and storage taxonomies.
The kind is the knowledge type; verification status is carried by where the item lives (worklog note = unverified candidate, capsule = verified).
`,ai-kb harvest` turns non-question notes into durable-memory candidates via its `structured_note` detector, keeping the kind verbatim;
`question` notes stay task-scoped context.
Use `anti_pattern` for approaches that were tried and rejected — the knowledge a future session would otherwise re-attempt —
and `recipe` for a working command/step sequence worth deferring to the verified-write path.
Front-load the literal identifiers a future query would use — the note text becomes the candidate title/body.
`wipe-current` deletes only the selected topic files (`.txt`, `.worklog.jsonl`, `.no_context`). It keeps other topics in the same workspace.
On default branches without an explicit active topic, it targets the latest `session-*` topic.

No hook runs on `stop`, and no hook re-prompts the agent.
Two disciplines that earlier lived in `stop` hooks now live in the SOP, enforced by instruction rather than by an auto-submitted follow-up:

- Evidence anchoring: visible factual/runtime claims must carry a hard source anchor or an explicit `Unknown` demotion (`~/CLAUDE.md` §2.1 / §2.3).
  The earlier `evidence_anchor.py` hook re-prompted per turn and was removed as noise.
- Durable-learning capture: as the last step of a substantive turn the agent self-vets and persists durable insights inline with `,ai-kb remember` (`~/CLAUDE.md` §4.1).
  This replaces the earlier `learning_reminder.py` stop hook, which auto-submitted a "persist learnings" prompt capped at once per conversation.
  The SOP habit has no cap and never injects a fake user turn.

On macOS, `/tmp` usually resolves to `/private/tmp`.
A temporary workspace like `/tmp/example` therefore records state under `/tmp/specs/private/tmp/example/`.
