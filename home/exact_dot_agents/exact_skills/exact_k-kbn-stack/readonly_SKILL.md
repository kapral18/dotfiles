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

Before starting, reusing, stopping, or pruning a stack, interpreting registry liveness/configuration, or selecting a browser target, MUST load and follow `~/.agents/skills/k-kbn-stack/references/runtime-lifecycle.md`.
Apply its Isolation Judgment before the start decision and its ownership rules before replacing or stopping anything.
Do not guess localhost ports or bypass per-worktree teardown.

`--status` works outside a Kibana worktree and lists every registry entry without changing it.
Its `ready`, `starting`, `degraded`, and `stale` states combine recorded readiness with current launcher/process and Kibana/Elasticsearch port liveness.

`--prune` works outside a Kibana worktree and removes only `stale` entries; it never stops processes.
Interactive ES and Kibana commands also invoke silent pruning when they exit, so the entry is removed after both halves are down while starting, ready, and degraded entries remain registered.

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
