---
name: k-tmux
description: "Use when running, probing, or automating tmux commands, panes, sessions, sockets, popups, capture-pane observations, source-file/config parsing, or interactive CLI workflows inside tmux."
---

# Tmux

Tmux is often the user's live terminal, not disposable infrastructure.
Treat the default tmux server as user-owned unless you prove otherwise.

## First Actions

1. Detect whether the agent is already inside tmux:
   - `$TMUX` set means the default server may be the user's live session.
   - `tmux display-message -p '#S #{socket_path}'` is a read-only identity probe for the current client.
2. Classify the operation before running it:
   - read-only observation of the current session
   - mutation of a verified current target
   - isolated config/probe work
   - interactive CLI driving
3. If the task only needs parsing, config loading, command syntax checks, or experiments, use an isolated socket and scratch session.
   Completion criterion: every tmux command in that probe includes the same `-S "$sock"` or `-L "$name"` selector, including cleanup.

## Default-Server Safety

- Never run bare `tmux kill-server`.
  `kill-server` is allowed only with an isolated `-S "$sock"` or `-L "$name"` selector that this agent created in the same step.
- Do not run bare server/session lifecycle or mutation commands against the default server (`new-session`, `kill-session`, `source-file`, `set-option`, `run-shell`, `display-popup`, `switch-client`, `attach`, `detach`, `send-keys`) unless the user explicitly asked to change the current tmux environment and the target was verified.
- Read-only commands against the current server are allowed when they are needed for observation:
  `display-message`, `list-sessions`, `list-windows`, `list-panes`, `capture-pane -p`, `show-options`, and `show-environment`.
  Keep target flags explicit when more than one session/window/pane exists.
- If `$TMUX` is set, a bare tmux command with no `-S`, `-L`, or explicit target is suspicious.
  Add the selector/target or stop and explain why the command must touch the live server.

## Isolated Probe Pattern

Use a scratch socket for config parsing, plugin option experiments, and source-file validation:

```bash
sock="$(mktemp -u "${TMPDIR:-/tmp}/agent-tmux.XXXXXX")"
tmux -S "$sock" -f /dev/null new-session -d -s agent-probe
tmux -S "$sock" source-file path/to/file.conf
tmux -S "$sock" show-options -gqv @some-option
tmux -S "$sock" kill-server
```

Do not mix isolated and default-server commands in one probe.
If cleanup uses `kill-server`, verify it carries the isolated selector before executing.

## Interactive CLI Workflow

Use tmux panes when an interactive CLI needs iterative observation and input, but isolate by default:

1. Create a dedicated, named session or window for the workflow, for example `agent-<topic>-<pid>`.
2. Start the CLI there rather than in the user's active pane unless the user asked you to take over that pane.
3. Observe with `tmux capture-pane -p -t <target>` and `tmux list-panes -F ...`; do not infer state from memory.
4. Send input with `tmux send-keys -t <target> ...` only after the target pane is named in the command and the captured output shows the CLI is waiting for that input.
5. Leave user-owned sessions running. Only tear down sessions/windows/panes that this agent created, and only by explicit target.

## Output

When tmux was touched, report:

- whether `$TMUX` was set
- the target server/session/window/pane or isolated socket used
- any mutation performed
- cleanup performed, or why user-owned tmux state was left alone
