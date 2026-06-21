---
sidebar_position: 1
title: Cursor and prompt wrap
---

# Cursor agent CLI

A cross-shell alias `agent` is provided for `cursor-agent`:

- POSIX interactive shells: [`home/readonly_dot_shellrc`](../../../../home/readonly_dot_shellrc) → `~/.shellrc`
- fish: [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../../home/dot_config/fish/readonly_config.fish.tmpl) → `~/.config/fish/config.fish`

```bash
command -v agent
agent --help
```

Cursor CLI is the primary interactive assistant harness. Its user-level hooks (session context, worklog) make up the hook-memory layer — documented in [Agent memory](../knowledge-base/index.md).

## Tmux agent prompt wrap

When running an AI coding agent (`claude`, `cursor-agent`, `pi`, or `copilot`) inside tmux, `Alt-Enter` is intercepted to prepend a calibrated verification scaffold and leave the prompt editable.

- **Binding:** `Alt-Enter` (inserts the wrapped prompt)
- **Toggle:** `prefix` + `W` (toggles wrapping on/off for the session)
- **Prefix text:** [`home/dot_config/exact_tmux/agent_prompts/prefix.txt`](../../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt)

Plain `Enter` is never touched. Press it when the wrapped prompt is ready to send. `Alt-Enter` is passed through untouched in non-agent panes or when the toggle is OFF.

The same `prefix.txt` is also injected automatically:

| Consumer                            | Injection path                                          |
| ----------------------------------- | ------------------------------------------------------- |
| `cursor-agent`, `claude`, `copilot` | `session_context.py` at `SessionStart`                  |
| `pi`                                | `ai-kb-recall.ts` at first `before_agent_start`         |
| custom subagents                    | rendered as the first body/developer-instructions block |

`Alt-Enter` remains the manual way to prepend the prefix to a specific prompt as a direct user message.
