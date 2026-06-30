---
name: kbn-stack
description: "Use when an elastic/kibana live UI or browser test needs local ES+Kibana URLs, -K runtime flags, kbn-stack registry checks, or stack start/stop/reuse."
tool_version: ",kbn-stack ownership registry surface verified 2026-06-30"
---

# Kbn Stack

Use `,kbn-stack` from an `elastic/kibana` git worktree to start an isolated local Elasticsearch + Kibana stack for that worktree.

## Use When

- A Kibana live UI flow needs a local `kbn_url` or `es_url`.
- A review or browser test needs Kibana running with specific `-K key=value` settings.
- You need to inspect or reuse `~/.cache/kbn-stack/registry.json`.
- The user asks to start, stop, or check a `,kbn-stack` stack.

## Do Not Use

- Non-Kibana repos.
- Production, shared cloud, or remote Kibana targets.
- `--stop-all` from an agent workflow. That is user-only cleanup.

## Command Surface

```bash
,kbn-stack
,kbn-stack --detach
,kbn-stack --stop
,kbn-stack --stop-all
,kbn-stack --es snapshot
,kbn-stack --es serverless --project-type es
,kbn-stack --data <name>
,kbn-stack --slot <n>
,kbn-stack -E key=value
,kbn-stack -K key=value
```

`--detach` is the agent mode: it starts ES and Kibana in the background, waits until Kibana answers `/api/status`, records `ready: true`, marks `started_by: "agent"`, and returns.

`-K key=value` is repeatable and becomes `--key=value` for `yarn start`.
Use it for runtime settings that the UI path requires, for example `-K xpack.index_management.dev.enableSemanticField=true`.

## Registry

The registry is `~/.cache/kbn-stack/registry.json`, keyed by the resolved absolute Kibana worktree path.

Each ready entry may include:

- `kbn_url`
- `es_url`
- `slot`
- `branch`
- `backend`
- `cookie_name`
- `kbn_flags`
- `ready`
- `started_by` (`"user"` for interactive/manual starts, `"agent"` for `--detach`)
- `start_mode` (`"interactive-tmux"`, `"manual-command"`, or `"agent-detach"`)
- `es_pid` / `kbn_pid` for detached stacks

Use only entries with `ready: true` as live browser targets. Do not guess localhost ports.
For older entries without `started_by`, infer `agent` only when recorded process ids are present; otherwise treat the entry as user-owned.

## Workflow

1. Verify the current directory is inside the intended Kibana git worktree with `git rev-parse --show-toplevel`.
2. Resolve the worktree path with `Path(...).resolve()` semantics; this is the registry key.
3. Inspect `~/.cache/kbn-stack/registry.json`.
4. If the matching entry is `ready: true` and has the needed `kbn_flags`, reuse it.
5. If no ready entry exists and shell side effects are allowed, run `,kbn-stack --detach` plus any required `-K key=value` flags.
6. If a ready stack with `started_by: "user"` is missing required `kbn_flags`, do not restart it.
   Report the exact `,kbn-stack --stop && ,kbn-stack --detach -K ...` command the user should run.
7. If a ready stack with `started_by: "agent"` is missing required `kbn_flags`, an agent may stop/recreate it only when that does not conflict with another active task; record the replacement in the evidence.
8. Load and follow the Playwriter skill before using `kbn_url` for readiness or UI verification.
9. If using `,artifact live`, inject the overlay only after Playwriter verifies the local/dev Kibana target.

## Teardown

- Track which registry entries existed before the worker ran and which entries the worker created with `started_by: "agent"`.
- If this agent started a detached stack, stop it with `,kbn-stack --stop` from the same worktree when verification is done.
- If the user already had a `started_by: "user"` stack, leave it running and report that it was reused.
- If a pre-existing `started_by: "agent"` stack is reused, leave it running unless this worker explicitly replaced it;
  report that it was reused as an agent-owned stack.
- Never stop stacks owned by other worktrees.
- Never run `,kbn-stack --stop-all` from an automated review or live-UI worker.

## Output

When reporting stack status, include:

- worktree path
- backend
- `kbn_url`
- `es_url`
- whether the stack was reused or started
- required `kbn_flags` parity
- teardown action taken or why it was left running
