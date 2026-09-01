---
name: k-kbn-stack
description: "Use for elastic/kibana UI/browser tests needing ES+Kibana URLs, -K flags, stack registry, start/stop/reuse."
tool_version: ",kbn-stack shared ES per package.json version + refcounted --stop verified 2026-09-01"
---

# Kbn Stack

Use `,kbn-stack` from an `elastic/kibana` git worktree to start a local Elasticsearch + Kibana stack for that worktree.
Each worktree always gets its own Kibana; default snapshot starts share one background ES per resolved ES version (see Shared ES below).

## Out Of Scope

- Non-Kibana repos.
- Production, shared cloud, or remote Kibana targets.
- `--stop-all` from an agent workflow. Use per-worktree `--stop`; `--stop-all` is user-only cleanup.

## Command Surface

```bash
,kbn-stack
,kbn-stack --detach
,kbn-stack --stop
,kbn-stack --stop-all
,kbn-stack --status
,kbn-stack --prune
,kbn-stack --es snapshot
,kbn-stack --es serverless --project-type es
,kbn-stack --isolated-es
,kbn-stack --data <name>
,kbn-stack --slot <n>
,kbn-stack -E key=value
,kbn-stack -K key=value
,kbn-stack --groups platform
,kbn-stack --groups all
,kbn-stack --groups platform,security
,kbn-stack --es-heap 1g
,kbn-stack --es-heap 1536m
```

`--detach` is the agent mode: it starts ES and Kibana in the background (attaching to a compatible live shared ES starts only Kibana), waits until Kibana answers `/api/status` and the port listener belongs to the spawned Kibana's process tree (a port-squatting orphan answering the probe is named and the stack is not marked ready), records `ready: true`, marks `started_by: "agent"`, and returns.
Starts also fail fast when a foreign process already holds the ports the start would bind, naming the owning pid to kill or stop first.

## Shared ES

Default snapshot starts reuse one background ES per resolved ES version — the worktree's `package.json` `version`, which is exactly what `yarn es snapshot` downloads.
The first compatible start creates the instance (registry key `__es__`, data dir `es_data/shared-<version>`);
later compatible starts attach only their Kibana to it.

- Sharing applies only when the start carries no ES-level override: any `-E`, `--data`, non-default `--es-heap`, or explicit `--isolated-es` starts an isolated per-worktree ES (the historical behavior).
  `-K` and `--groups` never affect sharing.
- Same-version Kibanas on one shared ES share the `.kibana*` saved-object indices (normal HA topology):
  saved objects created from one worktree are visible in the other.
  Do not use a shared ES when the verification needs saved-object or data isolation between worktrees;
  pass `--isolated-es` (see Isolation Judgment).
- If an attaching Kibana fails readiness with saved-object migration errors in its `kbn_log`, the branch's saved-object model clashes with the shared ES: rerun that worktree with `--isolated-es`.
  Do not stop the shared ES to resolve the clash; other worktrees may be attached.
- A shared ES with zero attached worktrees stays registered while alive and is reused by the next compatible start;
  `--prune` removes it only when dead.
- A share-eligible start first settles the worktree's previous non-shared stack:
  an orphaned isolated ES half (Kibana dead, no recorded process alive) is stopped so it cannot leak untracked, while a previous stack that is still owned — any recorded process alive, Kibana listening, or serverless containers up — fails the start and names `--stop` as the way forward (an isolated rerun would reuse the same slot and hit the same ports).

## Isolation Judgment

`,kbn-stack` gates sharing only on flags and the resolved ES version; it cannot see what the session will do to the cluster.
Judge isolation from the task's intent before starting, and pass `--isolated-es` when any signal below matches.

Isolate when the verification:

- asserts an empty state, first-use/onboarding flow, object counts, or list contents that another worktree's saved objects or indices would contaminate;
- creates, mutates, or deletes cluster-wide state: `_cluster/settings`, license level, security users/roles/realms, ILM/SLM policies, index or component templates, ingest pipelines, snapshots, or wildcard index deletes;
- exercises alerting rules, task manager, or background tasks — same-version Kibanas on one shared ES share the `.kibana_task_manager*` task pool, so any attached Kibana may claim and run the task under test instead of the one being observed;
- measures performance, query latency, or render timing, which load from other attached stacks would skew;
- reviews a diff that changes saved-object model versions/migrations or boot-time ES setup (index templates, ingest pipelines, Fleet package installs) — attaching that branch mutates shared state under the other worktrees.

Keep the shared default for read-mostly UI review, Dev Tools/Console checks, and flows over data the session itself seeds under uniquely named indices and saved objects.
When another worktree is attached and mid-verification with data assertions, prefer `--isolated-es` over adding churn to the shared cluster.
If an isolation signal surfaces only after start (the task turns out to mutate cluster state), stop that worktree's stack and restart it with `--isolated-es`.
Do not stop or restart the shared ES itself to resolve an isolation problem.

`--stop` and `--stop-all` SIGTERM the stack process group (the port listener's group for interactive tmux stacks), wait a short grace, then SIGKILL live members so a Kibana that logs "All plugins stopped" and hangs still exits.
On a shared-ES stack, `--stop` kills only that worktree's Kibana and refcounts the shared ES:
the instance keeps running while any other registered worktree references it, and the last detach stops it.
`--stop-all` clears every registered stack, including interactive tmux and shared ES instances.
From an agent workflow, use per-worktree `--stop`; `--stop-all` is user-only cleanup.

`-K key=value` is repeatable and becomes `--key=value` for `yarn start`.
Use it for runtime settings that the UI path requires, for example `-K xpack.index_management.dev.enableSemanticField=true`.

`--groups` defaults to `platform` and becomes `-K plugins.allowlistPluginGroups.N=<group>` (server plugin discovery only;
Rspack still compiles all UI). `--groups all` skips that allowlist so every group loads.
`--groups platform,security` loads those named groups.
Restart the stack to change groups; do not reuse a `platform`-only stack for a security/observability/search UI.
If the path under review is outside platform, pass `--groups all` (or the needed groups) on start.
An explicit `-K plugins.allowlistPluginGroups…` wins and `--groups` is not injected.

Snapshot ES sets `ES_JAVA_OPTS -Xms1g -Xmx1g` via `--es-heap` (default `1g`). `--es-heap 1536m` restores the kbn-es snapshot default.
`--es-heap` is snapshot-only; serverless docker already pins 1g.

Snapshot ES always includes `-E indices.merge.disk.watermark.high=2gb` before user `-E` flags.
That is an absolute free-space floor so overnight Kibana does not trip the parent circuit breaker when the Mac disk is above the default 95% merge watermark.
Override with a later `-E` of the same key.

`--status` works outside a Kibana worktree and lists every registry entry without changing it.
Its `ready`, `starting`, `degraded`, and `stale` states combine recorded readiness with current launcher/process and Kibana/Elasticsearch port liveness.

`--prune` works outside a Kibana worktree and removes only `stale` entries; it never stops processes.
Interactive ES and Kibana commands also invoke silent pruning when they exit, so the entry is removed after both halves are down while starting, ready, and degraded entries remain registered.

## Registry

The registry is `~/.cache/kbn-stack/registry.json`, keyed by the resolved absolute Kibana worktree path.
The reserved top-level key `__es__` maps ES version -> shared ES instance (`slot`, `es_url`, `es_http`, `data`, `log`, `es_pid`, `started_by`, `created_from`); every other top-level key is a worktree path.

Each ready worktree entry may include:

- `kbn_url`
- `es_url`
- `slot`
- `branch`
- `backend`
- `cookie_name`
- `kbn_flags`
- `kbn_log` for detached agent starts
- `ready`
- `started_by` (`"user"` for interactive/manual starts, `"agent"` for `--detach`)
- `start_mode` (`"interactive-tmux"`, `"manual-command"`, or `"agent-detach"`)
- `es_pid` / `kbn_pid` for detached stacks (shared-ES stacks record no `es_pid` on the worktree entry)
- `es_key` when the stack uses a shared ES (the `__es__` version key; `es_url` already points at that instance)

Use only entries with `ready: true` as live browser targets. Do not guess localhost ports.
For older entries without `started_by`, infer `agent` only when recorded process ids are present; otherwise treat the entry as user-owned.

## Workflow

1. Verify the current directory is inside the intended Kibana git worktree with `git rev-parse --show-toplevel`.
2. Resolve the worktree path with `Path(...).resolve()` semantics; this is the registry key.
3. Inspect `~/.cache/kbn-stack/registry.json`.
4. Before reusing a `ready: true` entry, correlate it with liveness/process evidence:
   recorded `kbn_pid`/`es_pid` when present, the derived Kibana/ES port listeners for the entry's `slot`, and relevant `log`/`kbn_log` paths.
   For an entry with `es_key`, take ES liveness from the `__es__` instance (its `es_http` listener or `es_pid`);
   do not derive it from the entry's slot, whose ES ports are unused.
   Do not use this to discover arbitrary localhost targets; use it only to validate or reject an existing registry entry keyed by worktree.
5. If the matching entry is `ready: true`, its Kibana/ES liveness matches the entry, and it has the needed `kbn_flags`, reuse it.
6. If no ready entry exists and shell side effects are allowed, run `,kbn-stack --detach` plus any required `-K key=value` flags.
   Pass `--groups all` (or the needed groups) when the UI under test is outside platform.
   Apply the Isolation Judgment section here: add `--isolated-es` when any of its signals matches the task.
7. If a ready stack with `started_by: "user"` is missing required `kbn_flags`, do not restart it.
   Report the exact `,kbn-stack --stop && ,kbn-stack --detach -K ...` command the user should run.
8. If a ready stack with `started_by: "agent"` is missing required `kbn_flags`, or its liveness/process evidence contradicts the registry, an agent may stop/recreate it only when that does not conflict with another active task; record the replacement in the evidence.
9. Load Playwriter before using `kbn_url` for readiness or UI verification.
10. If using `,artifact live`, inject the overlay only after Playwriter verifies the local/dev Kibana target.

## Teardown

- Track which registry entries existed before the worker ran and which entries the worker created with `started_by: "agent"`.
- If this agent started a detached stack, stop it with `,kbn-stack --stop` from the same worktree when verification is done.
  On a shared-ES stack this is safe by construction: `--stop` kills only this worktree's Kibana and stops the shared ES only when no other worktree references it.
- If the user already had a `started_by: "user"` stack, leave it running and report that it was reused.
- If a pre-existing `started_by: "agent"` stack is reused, leave it running unless this worker explicitly replaced it;
  report that it was reused as an agent-owned stack.
- Stop only stacks owned by this worktree. Never kill a shared ES process or its ports directly; teardown goes through `--stop` refcounting.
- Use per-worktree `,kbn-stack --stop` from automated review or live-UI workers; `,kbn-stack --stop-all` is user-only cleanup.

## Output

When reporting stack status, include:

- worktree path
- backend
- `kbn_url`
- `es_url`
- ES mode: shared (which `__es__` version, created or attached) or isolated
- whether the stack was reused or started
- required `kbn_flags` parity
- teardown action taken or why it was left running
