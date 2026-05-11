# Agent Hooks

Shared lifecycle hooks for terminal AI agents.

Cursor CLI is the primary runtime. Claude Code may reuse the subset with compatible schemas. Pi is intentionally not wired here because no hook lifecycle has been verified for it.

Runtime state is kept outside chezmoi and outside worktrees:

```text
/tmp/specs/<workspace-path-without-leading-slash>/_active_topic.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.worklog.jsonl
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.evidence_state.json
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.evidence_decisions.jsonl
```

The active topic is read from `_active_topic.txt` when present; otherwise hooks use `current`.

Default-branch workspaces are treated as shared scratch space. If the current git branch is `main`, `master`, `dev`, `develop`, or `trunk` and no explicit non-`current` topic is active, hook state uses a session-scoped topic (`session-<id>`) instead of the shared `current` topic. Feature/topic worktrees keep `current` continuity by default.

Session-start context is bounded without injecting partial memory. An oversized active topic spec is omitted with a pointer to the full file instead of being sliced into the prompt, and only whole recent worklog entries are included. Worklogs and evidence decision logs are also trimmed on write so runtime state does not grow forever.

Review topics run in clean-room mode by default. When the active topic name starts with `review` or the spec targets a PR, startup context keeps neutral metadata such as target, state, diff, and files, but omits prior `verified facts`, `findings`, `verdict`, inline comments, and recent worklog tails. Read the spec manually only when you intentionally want prior-session conclusions.

To start a clean session with no injected topic/worklog context, use one of:

```bash
AGENT_HOOK_CONTEXT=0 cursor-agent
touch /tmp/specs/<workspace-path-without-leading-slash>/_no_session_context
touch /tmp/specs/<workspace-path-without-leading-slash>/<topic>.no_context
```

The sentinel files are intentionally outside the worktree. Remove them to restore session context injection.

Use `,agent-memory` as a dead switch for persisted hook memory:

```bash
,agent-memory status
,agent-memory wipe-current
,agent-memory wipe-current --dry-run
,agent-memory wipe-current --reset-active
```

`wipe-current` deletes only the selected topic files (`.txt`, `.worklog.jsonl`, `.evidence_state.json`, `.evidence_decisions.jsonl`, `.no_context`). It keeps other topics in the same workspace. On default branches without an explicit active topic, it targets the latest `session-*` topic.

`evidence_state.json` stores the live per-turn claim ledger. `evidence_decisions.jsonl` records why each hook event was allowed, tracked, recorded as evidence, or converted into a follow-up. Tool/probe events are retained as evidence, but they do not clear all unresolved claims by themselves; visible response text must include local anchors or an explicit `Unknown` demotion for the relevant claim units.

On macOS, `/tmp` usually resolves to `/private/tmp`, so a temporary workspace like `/tmp/example` records state under `/tmp/specs/private/tmp/example/`.
