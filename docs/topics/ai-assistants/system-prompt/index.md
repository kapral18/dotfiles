---
title: System Prompt (SOP)
---

# System Prompt (SOP)

The SOP is the highest-leverage AI artifact in this setup. It decides how every harness interprets a request before a skill, subagent, model, or workflow gets involved.

| Slice                                                                   | Owns                                                                              |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| [Source of truth](source-of-truth.md)                                   | single file, symlink fan-out, and update workflow                                 |
| [Truth and verification](truth-and-verification.md)                     | compatibility, external truth, runtime truth, completion, compact-output recovery |
| [Execution workflow](execution-workflow.md)                             | reverse interview, persistent specs, verification loops, state-machine harnesses  |
| [Side-effect gates](side-effect-gates.md)                               | git push safety, ownership, publication, bot/human split                          |
| [Code-quality and dotfiles policy](code-quality-and-dotfiles-policy.md) | style matching, semantic dedupe, docs hygiene, shell/helper rules                 |

## Source map

| Surface           | Source                                                                                                             | Target                               |
| ----------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------ |
| Single SOP source | [`home/readonly_AGENTS.md`](../../../../home/readonly_AGENTS.md)                                                   | `~/AGENTS.md`                        |
| Claude            | [`home/symlink_CLAUDE.md`](../../../../home/symlink_CLAUDE.md)                                                     | `~/CLAUDE.md`                        |
| Gemini            | [`home/dot_gemini/symlink_GEMINI.md`](../../../../home/dot_gemini/symlink_GEMINI.md)                               | `~/.gemini/GEMINI.md`                |
| Cursor            | [`home/dot_cursor/symlink_AGENTS.md`](../../../../home/dot_cursor/symlink_AGENTS.md)                               | `~/.cursor/AGENTS.md`                |
| Codex             | [`home/dot_codex/symlink_AGENTS.md`](../../../../home/dot_codex/symlink_AGENTS.md)                                 | `~/.codex/AGENTS.md`                 |
| OpenCode          | [`home/dot_config/opencode/symlink_AGENTS.md`](../../../../home/dot_config/opencode/symlink_AGENTS.md)             | `~/.config/opencode/AGENTS.md`       |
| Copilot           | [`home/dot_copilot/symlink_copilot-instructions.md`](../../../../home/dot_copilot/symlink_copilot-instructions.md) | `~/.copilot/copilot-instructions.md` |

## Mental model

1. SOP sets global invariants.
2. [Skills](../skills/index.md) add intent-specific procedures.
3. [Subagents](../subagents.md) isolate heavy or parallel work.
4. Workflow pages explain the common composed flows.

## Related

- [Skills](../skills/index.md)
- [Cross-harness subagents](../subagents.md)
- [Agent memory](../knowledge-base/index.md)
