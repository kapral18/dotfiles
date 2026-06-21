---
sidebar_position: 1
title: Hook memory
---

# Hook memory (`/tmp/specs`, `,agent-memory`)

Cursor CLI is the primary interactive assistant harness.

| Surface             | Source                                                                                 | Target                 |
| ------------------- | -------------------------------------------------------------------------------------- | ---------------------- |
| Cursor hooks        | [`home/dot_cursor/hooks.json`](../../../../home/dot_cursor/hooks.json)                 | `~/.cursor/hooks.json` |
| Shared hook scripts | [`home/exact_dot_agents/exact_hooks/`](../../../../home/exact_dot_agents/exact_hooks/) | `~/.agents/hooks/`     |

The hook layer is Cursor-native first:

| Event                                                                       | Script                | Purpose                                                                                                                                                                                                                                                   |
| --------------------------------------------------------------------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sessionStart`                                                              | `session_context.py`  | Inject the verification-discipline prefix (`prefix.txt`); inject the active `/tmp/specs` topic spec plus recent worklog tail when present; nudge to set a named topic on shared-branch sessions; remind to recall/remember durable knowledge via `,ai-kb` |
| `afterShellExecution`, `postToolUse`, `postToolUseFailure`, `afterFileEdit` | `worklog_recorder.py` | Append compact per-topic JSONL worklog entries                                                                                                                                                                                                            |

OpenCode reuses both scripts through [`agent-memory.ts`](../../../../home/dot_config/opencode/plugins/agent-memory.ts):

| OpenCode hook                        | What it does                                                                                  |
| ------------------------------------ | --------------------------------------------------------------------------------------------- |
| `experimental.chat.system.transform` | Fetches `session_context.py` once per session and appends it to every request's system prompt |
| `tool.execute.after`                 | Feeds `worklog_recorder.py` a synthesized `PostToolUse` payload                               |

`duration` and `status` are not exposed by the OpenCode plugin API and are omitted.

Codex has the same wiring in [`home/dot_codex/hooks.json`](../../../../home/dot_codex/hooks.json):

| Codex event    | Script                |
| -------------- | --------------------- |
| `SessionStart` | `session_context.py`  |
| `PostToolUse`  | `worklog_recorder.py` |

Payload shapes are Claude-compatible as of codex source tag `rust-v0.139.0`. Hook trust hashes are baked into config templates because the codex merge script regenerates `config.toml` wholesale.

**Caveat:** `codex exec` 0.139.0 was verified to dispatch no hooks, even with `--dangerously-bypass-hook-trust` and `[features] hooks = true`. This wiring is currently inert in exec mode. For interactive TUI sessions, run `/hooks` and verify both hooks are trusted and fire.

No hook runs on `stop`. Hooks observe and inject context; they do not re-prompt the agent. Two disciplines that earlier lived in `stop` hooks now live in the SOP, enforced by instruction rather than by an auto-submitted follow-up message:

- **Evidence anchoring** — a factual/runtime claim must carry a hard source anchor (file path, command/probe output, test result, or freshly fetched docs URL) or be explicitly demoted to `Unknown` with a reason (`~/CLAUDE.md` §2.1 External Truth / §2.3 Completion). The earlier `evidence_anchor.py` hook re-prompted per turn and was removed as noise.
- **Durable-learning capture** — as the last step of any substantive turn, the agent self-vets whether it produced a durable, verified, reusable insight and, if so, persists it inline with `,ai-kb remember` (`~/CLAUDE.md` §4.3, mirrored in `~/AGENTS.md` / `~/.gemini/GEMINI.md`). This replaces the earlier `learning_reminder.py` `stop` hook, whose auto-submitted "persist learnings" prompt was both intrusive and capped at once per conversation. The SOP habit has no per-session cap and never injects a fake user turn.

At session start, interactive harnesses inject the verification-discipline prefix from [`prefix.txt`](../../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt).

| Consumer                                   | How it gets `prefix.txt`                                                       |
| ------------------------------------------ | ------------------------------------------------------------------------------ |
| Cursor/Claude/Copilot-style hook harnesses | `session_context.py` reads it at runtime                                       |
| Pi                                         | `ai-kb-recall.ts` injects it at first `before_agent_start`                     |
| Custom subagents                           | profile templates render it as the first body/developer-instructions block     |
| tmux manual prompt wrap                    | `Alt-Enter` pastes the same text; see [Tool configs](../tool-configs/index.md) |

`cursor-agent` has no per-prompt context-injection hook; `beforeSubmitPrompt` is allow/block only. Pi could inject the prefix per turn but intentionally does not, avoiding repeated fixed text.

Runtime state is intentionally outside chezmoi and outside worktrees:

```text
/tmp/specs/<workspace-path-without-leading-slash>/_active_topic.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.worklog.jsonl
```

Bounded-context rules:

| Rule                                                         | Why                                                           |
| ------------------------------------------------------------ | ------------------------------------------------------------- |
| Oversized specs are omitted with a pointer                   | Avoid slicing partial memory into the prompt                  |
| Only whole recent worklog entries are included               | Avoid half-events that mislead the agent                      |
| Worklog JSONL files trim on write                            | Keep startup injection bounded                                |
| Shared default branches use session-scoped topics by default | Prevent unrelated `main` sessions inheriting `current` memory |
| Feature/topic worktrees keep `current` continuity            | Preserve useful project continuity in isolated worktrees      |
| Review topics run clean-room by default                      | Reduce bias in re-reviews                                     |

On shared branches (`main`, `master`, `dev`, `develop`, `trunk`) with no explicit non-`current` topic, `session_context.py` injects a nudge to set a named topic. That recovers continuity on `main` without cross-contaminating unrelated work.

Force a clean session with either:

```bash
AGENT_HOOK_CONTEXT=0
```

or by placing `_no_session_context` / `<topic>.no_context` under the workspace's `/tmp/specs/...` directory.

The user-facing control plane is `,agent-memory`:

| Command                      | Effect                                                                       |
| ---------------------------- | ---------------------------------------------------------------------------- |
| `,agent-memory status`       | Show the selected workspace topic                                            |
| `,agent-memory use <topic>`  | Pin a named active topic; writes `_active_topic.txt` and seeds `<topic>.txt` |
| `,agent-memory wipe-current` | Delete the selected topic's spec, worklog, and no-context sentinel           |

Sources:

- [`home/exact_bin/executable_,agent-memory`](../../../../home/exact_bin/executable_,agent-memory)
- [`scripts/agent_memory.py`](../../../../scripts/agent_memory.py)
- [`home/dot_config/fish/completions/readonly_,agent-memory.fish`](../../../../home/dot_config/fish/completions/readonly_,agent-memory.fish)

`use <topic>` rejects the generic `current`, giving shared-branch sessions distinct continuity. On default branches without an explicit active topic, `wipe-current` targets the latest `session-*` topic.

Claude Code mirrors only the proven shared subset through `settings.personal.json` and `settings.work.json`: session context and tool worklog recording. The local llama.cpp settings file is intentionally excluded. Pi has no verified hook lifecycle, so it remains static-prompt only.

Verification:

```bash
python3 scripts/tests/test_agent_hooks.py
chezmoi diff --no-pager
chezmoi apply --force --no-tty
,agent-memory status
```
