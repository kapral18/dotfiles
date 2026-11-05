---
name: k-herdr
description: "Use when inspecting or driving herdr workspaces, tabs, panes, or agents, or probing herdr config, plugins, or sessions."
---

# Herdr

herdr is the user's live terminal: the default session holds every workspace, pane, and agent they have open.
Treat it as user-owned unless you created the target.

## First actions

1. `test "${HERDR_ENV:-}" = 1` tells you this agent runs inside a herdr pane; `HERDR_PANE_ID` and `HERDR_WORKSPACE_ID` name it.
2. Run `herdr --skill` once for the command reference, then `herdr <group>` (for example `herdr pane`) for a group's syntax.
   Never run bare `herdr` to discover commands: it attaches the TUI.
3. Classify the operation: read-only observation, work in targets you create, or a change to a target the user owns.

## Default-session safety

- Never run `herdr server stop` without `--session`: it ends every pane the user has.
- Close, stop, or reload (`workspace close`, `tab close`, `pane close`, `worktree remove`, `session stop|delete`, `server reload-config`, `config reset-keys`, plugin unlink/disable) only for a target you created or the user named, after reading it from `herdr workspace list` / `herdr pane list`.
- Read-only commands are fine for observation: `workspace list|get`, `tab list`, `pane list|get|read|process-info`, `agent list|get|read`, `status`.

## Isolated probes

Config, plugin, and lifecycle experiments run on a scratch session; every command in the probe carries the same `--session`:

```bash
herdr config check                       # validates config.toml without a server
herdr --session agent-probe server &     # the CLI never starts a server itself
for _ in $(seq 50); do herdr --session agent-probe workspace list > /dev/null 2>&1 && break; sleep 0.1; done
herdr --session agent-probe workspace create --label probe --no-focus
herdr --session agent-probe pane list
herdr --session agent-probe server stop  # ends that server and its panes
```

`default` names the user's own session: `--session default` is not isolation.

## Driving CLIs and agents

1. Create your own tab or pane (`herdr tab create --no-focus`, `herdr pane split --no-focus`) unless the user asked you to use theirs.
2. Observe with `herdr pane read` or `herdr pane wait-output`; use `herdr agent wait` for agent state. Do not infer state from memory.
3. Send input with `herdr pane run` (text plus Enter) or `pane send-keys` only to a pane whose output shows it is waiting.
4. Close only what you created, by explicit id.

## Output

When herdr was touched, report: whether `HERDR_ENV` was set, the session/workspace/pane ids used, any change made, and the cleanup done.
