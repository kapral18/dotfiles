# Agent Hooks

Shared lifecycle hooks for terminal AI agents.

Cursor CLI is the primary runtime. Claude Code, Codex, Antigravity, OpenCode, and Copilot reuse compatible shared scripts.
Those scripts cover bounded session context, compaction reinforcement, correction hints, and worklog recording.
Each adapter passes its native session ID so topic selection, worklogs, and recall dedupe use the same binding.
PR review anchor verification is instruction-owned by the review/GitHub skills, not enforced by a shell hook.
Pi does not use this `hooks.json`-style lifecycle; it has its own TypeScript extension API.
Pi's session-context integration therefore lives in a pi extension (`home/dot_pi/agent/exact_extensions/ai-kb-recall.ts`) rather than here.
That extension reuses the same `/tmp/specs` topic resolution (via `,agent-memory status --json --session-id <id>`) and forwards `tool_result` events to `worklog_dispatcher.sh` so pi sessions feed the shared worklog trail.
This keeps behavior consistent across runtimes — see the cross-agent memory doc for the root-owned durable-memory boundary.

Runtime state is kept outside chezmoi and outside worktrees:

```text
/tmp/specs/<workspace-path-without-leading-slash>/_active_topic.txt
/tmp/specs/<workspace-path-without-leading-slash>/.session-topic-<session-id>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.worklog.jsonl
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
On a feature branch, a session with no binding joins the newest bucket automatically through `,agent-memory select` (or stays on `current` when no named bucket exists), so no model turn is spent on the picker.
On a default branch the picker stays, because parallel sessions work on different threads there;
the index says `current` is refused, asks for the bind in the same tool batch as the first investigation command, and a prompt that names a bucket (slug or spec path) binds automatically from `perturn_recall.py`.
A bound root session stages filtered recall and emits an admission pointer once per session-topic binding; later staging is silent.
The list is sorted newest-first by the most recent spec/worklog update and shows a short summary derived from `summary:` (preferred) or `target:`/`action:` lines in the topic spec.
Add `summary: <one-line label>` to persist a concise description alongside the topic name.
The agent should bind automatically when exactly one bucket clearly matches the user's request, create a new bucket when none matches, and ask one question only when multiple buckets plausibly match.
It then runs `,agent-memory select <topic> [--create] --session-id <id>` itself.
Feature/topic worktrees keep `current` continuity by default when no `_active_topic.txt` hint is present.

Copilot sub-agents run with `COPILOT_AGENT_SESSION_ID` set to the parent session id.
Worklog writes (`worklog_recorder.py` via `topic_paths_for_write`) and the `,agent-memory` CLI resolve the parent's selected topic, or its `session-<parent>` fallback on default branches, so sub-agent activity lands in the parent's bucket.
Hook topic resolution ignores it, so blind lanes receive no parent context; `session_context.is_delegated_leaf()` reads it to suppress the delegation blocks below.

Session-bound topics receive bounded spec/worklog context.
Startup BM25 and per-turn hybrid retrieval stage complete relevance/workspace-filtered candidates;
capsule bodies stay outside the main prompt.
The root owns admission through `k-ai-kb`, with one pointer per binding, not an agent per prompt.
Genuine corrections retain `,agent-memory note anti_pattern` capture; verified reusable insights are persisted in one final learning batch.
Known leaves skip retrieval and root workflow hints; worklog capture remains independent.

Per-turn recall also carries the probe-budget hint: `,probe fail` appends to `<spec_dir>/<session_key>.probe-ledger.jsonl` (agents record failures only, chained onto the failing command), and `correction_detector.probe_budget_signal` fires `probe-budget-exhausted` when 3+ of the last 8 entries are failures recorded within the last 30 minutes.
Because a plain shell usually has no harness session id, `,probe` writes under the `ad-hoc` key;
the reader falls back to that shared ledger when the session-keyed one is missing or empty;
the same 30-minute failure window keeps another session's stale failures from firing the hint.
The pi/omp `ai-kb-recall.ts` mirrors carry the same consumer with identical thresholds and note text.
Antigravity has no user-prompt hook, so `premise_nudge.py` computes the signal during its `PreInvocation` drain and injects the note alongside any queued premise nudges.

`AI_AGENT_DEPTH` retains fast/balanced/deep retrieval settings; fast skips retrieval and warm-up.
Adapters request bounded embedder warm-up through their existing flags; hybrid searches use connect-only access and fail-open re-warm.
Hooks never start another agent or re-prompt. Admission and batched learning follow the root-only skill contract.

The deployed `~/lib/,ai-kb/embed_client.py` selects a generation-specific Unix socket from protocol version, complete worker source, model, and expected dimension.
Warm-up resolves the configured model dimension; connect-only callers discover the matching ready generation without spawning.
Its user-owned runtime root is `0700`, the socket and start lock are `0600`, startup markers are atomically published and tied to the expected worker command, resident socket messages are bounded, and the worker never logs or echoes their prompt text.
One default BGE-small worker measured about 320 MiB RSS; two coexisting deployment generations measured about 625 MiB total.
The worker exits after 300 inactive seconds while removing only its own socket inode.

Session-start context is bounded without injecting partial memory.
An oversized active topic spec is omitted with a pointer to the full file instead of being sliced into the prompt.
Only whole recent worklog entries are included; omission notices count against the same cap.
Cursor startup additionally enforces its 10,000 UTF-16-unit carrier limit: omit whole optional worklog, spec, or bucket blocks with file pointers before rejecting oversized mandatory instructions.
Never slice the mandatory instructions to fit the carrier.

Session start injects no verification prefix: the full SOP is fresh at the top of a new session.
`reinforcement.py` (called from `perturn_recall.py`) re-injects the compiler-verified `prefix.txt` excerpt only after the context grew by 200k tokens since the last injection or after a compaction.
Growth is read from the Claude transcript (`message.usage`) or the Codex rollout (`token_count`);
harnesses without a usage signal fall back to a prompt interval.
A `SessionStart` with `source=compact` marks the next prompt for re-injection.
State is `<session-key>.reinforce.json` next to the topic spec; every failure path is fail-open.
Worklogs are trimmed during serialized queue flush so runtime state does not grow forever.
The same flush pass also removes `session-*` fallback worklogs and per-session recall state (`.recall-seen-*`, `.recall-candidates-*`, `.recall-staged-*`, `.recall-pointed-*`, `.recall-warm-*`) older than seven days; named-topic worklogs are never swept.

`read_gate.py` refuses a second whole-file read whose bytes match an earlier read in the same context, naming that read and the escape hatches (offset/limit or any ranged read, `sed -n`, `AGENT_READ_GATE=off`).
Before refusing it re-opens the history store and checks that the recorded result still reproduces the file;
a truncated preview, missing row, or garbled copy allows the read silently and notes the reason in the ledger.
A changed file is always allowed with a "changed since your read" note. First reads, slices, pipes and redirects are never touched.
Ledger `.reads-<context>.json` is keyed by child `agent_id` (Claude Code passes the parent's `transcript_path` for children) or by session;
entries from before a compaction epoch never block.
Coverage: Claude Code and Codex (hooks.json), Pi (`read-gate.ts`), Cursor (`beforeReadFile`/shell events, history in `~/.config/cursor/chats/*/<conversation_id>/store.db`, `stop` token shrink = compaction), Copilot (extension `onPreToolUse`/`onPostToolUse`, history in `session-state/<id>/events.jsonl`, `session.compaction_complete` resets).
OMP supersedes earlier reads itself and is left alone; Pi and OpenCode get the same via their `read-supersede.ts` (older results of a re-read file become a notice on the outgoing list, with OMP's cache guard); OpenCode is gated by `plugins/agent-memory.ts` (`tool.execute.before` throws the reason; history is the `part` table of `opencode.db`); Antigravity is unwired.

`publish_gate.py` is the deterministic backstop for SOP §3.8 and the §3.7 leaf contract.
It recognises publication calls (`gh pr|issue|release|gist` mutating verbs, non-GET `gh api` REST calls with a body, `gh api graphql` mutations, `gws gmail`/`gws chat` sends, Slack MCP mutation tools) and denies them from a delegated leaf (Claude Code child `agent_id`, Copilot parent session, pi child); read-only calls are never touched.
For the root it allows the call and rides a short §3.8 checklist (approved exact target/payload, `k-communication` wording without session artifacts, read-back) as `additionalContext`; `AGENT_PUBLISH_GATE_ROOT=ask` turns that into a harness confirmation, `AGENT_PUBLISH_GATE=off` disables the hook.
Coverage: Claude Code (`Bash|mcp__slack__.*`) and Codex (`Bash|shell`, `hook_specific` output);
other harnesses are unwired and keep the prose boundary plus a `disallowedTools` denial of the six Slack mutation tools (reads stay available) on the Claude profiles that inherit every tool.

Tool adapters invoke `worklog_dispatcher.sh`, which captures the JSON payload and launches `worklog_recorder.py` without waiting for filesystem bookkeeping.
The recorder durably enqueues a session-sequenced event, and a transient worker flushes it under a per-target lock.
Queue records are atomically published and fsynced; stable IDs make crash replay idempotent, and target output is timestamp-ordered for harvest.
Pending state is capped at 256 events and 1 MiB per session, output at 200 records, worker lifetime at 80ms idle/two seconds total, and drained queue/error directories at seven days.
Failures stay in bounded error ledgers: agents fail open, session startup warns, and `,ai-kb harvest` refuses to report success while pending/error state remains.

Review topics run in clean-room mode by default.
When the active topic name starts with `review` or the spec targets a PR, startup context keeps neutral metadata such as target, state, diff, and files.
It omits prior `verified facts`, `findings`, `verdict`, inline comments, and recent worklog tails.
Plain headings and ATX headings at levels 1–6, including closing hashes, select the same clean-room sections.
Read the spec manually only when you intentionally want prior-session conclusions.

To start a clean session with no injected topic/worklog context, use one of:

```bash
AGENT_HOOK_CONTEXT=0 cursor-agent
touch /tmp/specs/<workspace-path-without-leading-slash>/_no_session_context
touch /tmp/specs/<workspace-path-without-leading-slash>/<topic>.no_context
```

The sentinel files are intentionally outside the worktree. Remove them to restore session context injection.
Disable checks apply on every turn, including correction, growth, and compaction paths;
worklog recording and native SOP loading remain active.
Removing a live topic sentinel also retires its mirrored copy; whole-topic loss still restores the sentinel with the topic.
Pi/OMP register shared context, correction, and worklog callbacks even when `,ai-kb` is unavailable; only retrieval and warm-up are skipped.

The standalone `,agent-memory` launcher uses `~/lib/,agent-memory/`; it requires no source checkout or runtime chezmoi lookup.

Use `,agent-memory` to set the active topic or as a dead switch for persisted hook memory:

```bash
,agent-memory status --session-id <id>
,agent-memory select <topic> --session-id <id>
,agent-memory select <new-topic> --create --session-id <id>
,agent-memory use <topic>
,agent-memory merge <source-topic> <dest-topic> [--dry-run]
,agent-memory note <fact|gotcha|pattern|anti_pattern|recipe|principle|question|decision> "<text>" [--ref <anchor>]
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
`--reset-active` removes both live and mirrored active pointers, even when the live pointer is already absent;
ordinary wipe and dry-run preserve them.

No hook runs on `stop`, and no hook re-prompts the agent.
Two disciplines that earlier lived in `stop` hooks now live in the SOP, enforced by instruction rather than by an auto-submitted follow-up:

- Evidence anchoring: visible factual/runtime claims must carry a hard source anchor or an explicit `Unknown` demotion (`~/AGENTS.md` §2.2 / §2.6).
  The earlier `evidence_anchor.py` hook re-prompted per turn and was removed as noise.
- Durable-learning capture remains required for verified reusable insights through the final `k-ai-kb` batch;
  no per-turn scribe or follow-up prompt is introduced.

On macOS, `/tmp` usually resolves to `/private/tmp`.
A temporary workspace like `/tmp/example` therefore records state under `/tmp/specs/private/tmp/example/`.
