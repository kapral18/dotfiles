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

When running an AI coding agent (`claude`, `cursor-agent`, or `pi`) in the foreground of a tmux pane, `Alt-Enter` is intercepted to prepend a compact verification discipline and leave the prompt editable.

- **Binding:** `Alt-Enter` (inserts the wrapped prompt)
- **Toggle:** `prefix` + `W` (toggles wrapping on/off for the session)
- **Prefix text:** [`home/dot_config/exact_tmux/agent_prompts/prefix.txt`](../../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt)

Plain `Enter` is never touched. Press it when the wrapped prompt is ready to send. `Alt-Enter` is passed through untouched in non-agent panes or when the toggle is OFF. Background or stopped agents do not activate wrapping.

`prefix.txt` is a compiler-verified excerpt of the SOP (`compile_ai_policy.py verify` rejects any sentence that is not verbatim SOP text). It is also injected automatically, but never at session start, where the full SOP is fresh:

| Consumer          | Injection path                                                                                                                                                                        |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `claude`, `codex` | per-prompt hook `perturn_recall.py` re-injects after a compaction, or a large drop in observed context tokens (Claude transcript / Codex rollout usage) that reads as the same signal |
| `cursor-agent`    | same hook, but its payload carries no transcript, so no mid-session re-injection fires; only a fresh session shows the full SOP                                                       |
| `pi`, `omp`       | `ai-kb-recall.ts` re-injects only on the native `session_compact` event                                                                                                               |
| custom subagents  | render the sibling `leaf-boundary.txt` (SOP §3.7 leaf-worker boundary) as the first body/developer-instructions block                                                                 |

Tuning: `AGENT_REINFORCE=off` disables re-injection. State lives in `<session-key>.reinforce.json` next to the topic spec.

`Alt-Enter` remains the manual way to prepend the prefix to a specific prompt as a direct user message.
