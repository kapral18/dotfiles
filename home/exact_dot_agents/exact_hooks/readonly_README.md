# Agent Hooks

Shared lifecycle hooks for terminal AI agents.

Cursor CLI is the primary runtime. Claude Code, Codex, Gemini, OpenCode, and Copilot reuse compatible shared scripts.
Those scripts cover session context, per-turn recall where supported, and worklog recording.
Each adapter passes its native session ID so topic selection, worklogs, and recall dedupe use the same binding.
PR review anchor verification is instruction-owned by the review/GitHub skills, not enforced by a shell hook.
Pi does not use this `hooks.json`-style lifecycle; it has its own TypeScript extension API.
Pi's durable-memory recall therefore lives in a pi extension (`home/dot_pi/agent/extensions/ai-kb-recall.ts`) rather than here.
That extension reuses the same `/tmp/specs` topic resolution (via `,agent-memory status --json --session-id <id>`) and the same `,ai-kb` retrieval.
This keeps behavior consistent across runtimes — see the AI knowledge base doc for the cross-runtime retrieval table.

Runtime state is kept outside chezmoi and outside worktrees:

```text
/tmp/specs/<workspace-path-without-leading-slash>/_active_topic.txt
/tmp/specs/<workspace-path-without-leading-slash>/.session-topic-<session-id>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.worklog.jsonl
/tmp/specs/<workspace-path-without-leading-slash>/.recall-seen-<session-key>.json
```

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
It surfaces up to three capsules that are local to this workspace or scoped `domain`/`universal`, so durable memory seeds the session automatically.
Unbound, ad-hoc/`session-*`, and review topics get no warm-start. This is the only automatic KB retrieval.
Cursor cannot inject context per-turn (`beforeSubmitPrompt` carries no context-injection output), so mid-task relevance comes from the agent's own `,ai-kb search` calls against its actual task.
The hook reads the KB but never writes it; persistence stays agent-driven.
Warm-start and per-turn recall persist injected capsule IDs in `.recall-seen-<session-key>.json`.
The canonical session key follows `conversation_id`, then `session_id`, then `generation_id`;
Pi persists the same state across extension reloads and session resumes.

Session-start context is bounded without injecting partial memory.
An oversized active topic spec is omitted with a pointer to the full file instead of being sliced into the prompt.
Only whole recent worklog entries are included. Worklogs are also trimmed on write so runtime state does not grow forever.

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
,agent-memory wipe-current
,agent-memory wipe-current --dry-run
,agent-memory wipe-current --reset-active
```

`select` binds one agent session to a topic bucket by writing `.session-topic-<session-id>.txt`.
It seeds `<topic>.txt` only with `--create`.
`use` manages the workspace-level default/suggested bucket: it writes `_active_topic.txt` and seeds `<topic>.txt` (rejecting the generic `current`).
Use it only when you intentionally want to mark a default/suggested bucket for the workspace.
`wipe-current` deletes only the selected topic files (`.txt`, `.worklog.jsonl`, `.no_context`). It keeps other topics in the same workspace.
On default branches without an explicit active topic, it targets the latest `session-*` topic.

No hook runs on `stop`, and no hook re-prompts the agent.
Two disciplines that earlier lived in `stop` hooks now live in the SOP, enforced by instruction rather than by an auto-submitted follow-up:

- Evidence anchoring: visible factual/runtime claims must carry a hard source anchor or an explicit `Unknown` demotion (`~/CLAUDE.md` §2.1 / §2.3).
  The earlier `evidence_anchor.py` hook re-prompted per turn and was removed as noise.
- Durable-learning capture: as the last step of a substantive turn the agent self-vets and persists durable insights inline with `,ai-kb remember` (`~/CLAUDE.md` §4.3).
  This replaces the earlier `learning_reminder.py` stop hook, which auto-submitted a "persist learnings" prompt capped at once per conversation.
  The SOP habit has no cap and never injects a fake user turn.

On macOS, `/tmp` usually resolves to `/private/tmp`.
A temporary workspace like `/tmp/example` therefore records state under `/tmp/specs/private/tmp/example/`.
