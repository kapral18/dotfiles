# Agent Hooks

Shared lifecycle hooks for terminal AI agents.

Cursor CLI is the primary runtime. Claude Code, Codex, Gemini, OpenCode, and Copilot reuse compatible shared scripts for session context, per-turn recall where supported, and worklog recording. Harness-specific hook adapters live with that harness' config source; for example, Copilot's `permissionDecision` PR anchor gate is sourced from `home/dot_copilot/exact_hooks/` and deploys to `~/.copilot/hooks/`, not `~/.agents/hooks/`. Pi does not use this `hooks.json`-style lifecycle; it has its own TypeScript extension API, so pi's durable-memory recall lives in a pi extension (`home/dot_pi/agent/extensions/ai-kb-recall.ts`) rather than here. That extension reuses the same `/tmp/specs` topic resolution (via `,agent-memory status --json`) and the same `,ai-kb` retrieval, so behavior stays consistent across runtimes — see the AI knowledge base doc for the cross-runtime retrieval table.

Runtime state is kept outside chezmoi and outside worktrees:

```text
/tmp/specs/<workspace-path-without-leading-slash>/_active_topic.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.worklog.jsonl
```

The active topic is read from `_active_topic.txt` when present; otherwise hooks use `current`. Set a named topic with `,agent-memory use <topic>`.

Default-branch workspaces are treated as shared scratch space. If the current git branch is `main`, `master`, `dev`, `develop`, or `trunk` and no explicit non-`current` topic is active, hook state uses a session-scoped topic (`session-<id>`) instead of the shared `current` topic. Feature/topic worktrees keep `current` continuity by default. On a shared-branch session that falls back to a `session-*` topic, `session_context.py` injects a one-line nudge to set a named topic with `,agent-memory use <topic>` — that is how continuity is recovered on `main` without cross-contaminating other work on the same branch.

For a deliberate named topic (the active topic is neither `current` nor a `session-*` fallback) with a non-empty `<topic>.txt` spec, `session_context.py` also injects a relevance-gated `### Relevant Learnings (,ai-kb)` block: it runs `,ai-kb search` with the spec text as the query (`bm25` lane, no embedder, bounded by the hook timeout) and surfaces up to three capsules that are local to this workspace or scoped `domain`/`universal`, so durable memory seeds the session automatically. Ad-hoc/`session-*` and review topics get no warm-start. This is the only automatic KB retrieval — Cursor cannot inject context per-turn (`beforeSubmitPrompt` carries no context-injection output), so mid-task relevance comes from the agent's own `,ai-kb search` calls against its actual task. The hook reads the KB but never writes it; persistence stays agent-driven.

Session-start context is bounded without injecting partial memory. An oversized active topic spec is omitted with a pointer to the full file instead of being sliced into the prompt, and only whole recent worklog entries are included. Worklogs are also trimmed on write so runtime state does not grow forever.

Review topics run in clean-room mode by default. When the active topic name starts with `review` or the spec targets a PR, startup context keeps neutral metadata such as target, state, diff, and files, but omits prior `verified facts`, `findings`, `verdict`, inline comments, and recent worklog tails. Read the spec manually only when you intentionally want prior-session conclusions.

To start a clean session with no injected topic/worklog context, use one of:

```bash
AGENT_HOOK_CONTEXT=0 cursor-agent
touch /tmp/specs/<workspace-path-without-leading-slash>/_no_session_context
touch /tmp/specs/<workspace-path-without-leading-slash>/<topic>.no_context
```

The sentinel files are intentionally outside the worktree. Remove them to restore session context injection.

Use `,agent-memory` to set the active topic or as a dead switch for persisted hook memory:

```bash
,agent-memory status
,agent-memory use <topic>
,agent-memory wipe-current
,agent-memory wipe-current --dry-run
,agent-memory wipe-current --reset-active
```

`use` pins a named active topic: it writes `_active_topic.txt` and seeds `<topic>.txt` (rejecting the generic `current`), giving shared-branch sessions distinct, contamination-free continuity. `wipe-current` deletes only the selected topic files (`.txt`, `.worklog.jsonl`, `.no_context`). It keeps other topics in the same workspace. On default branches without an explicit active topic, it targets the latest `session-*` topic.

No hook runs on `stop`, and no hook re-prompts the agent. Two disciplines that earlier lived in `stop` hooks now live in the SOP, enforced by instruction rather than by an auto-submitted follow-up:

- Evidence anchoring: visible factual/runtime claims must carry a hard source anchor or an explicit `Unknown` demotion (`~/CLAUDE.md` §2.1 / §2.3). The earlier `evidence_anchor.py` hook re-prompted per turn and was removed as noise.
- Durable-learning capture: as the last step of a substantive turn the agent self-vets and persists durable insights inline with `,ai-kb remember` (`~/CLAUDE.md` §4.3). This replaces the earlier `learning_reminder.py` stop hook, which auto-submitted a "persist learnings" prompt capped at once per conversation; the SOP habit has no cap and never injects a fake user turn.

On macOS, `/tmp` usually resolves to `/private/tmp`, so a temporary workspace like `/tmp/example` records state under `/tmp/specs/private/tmp/example/`.
