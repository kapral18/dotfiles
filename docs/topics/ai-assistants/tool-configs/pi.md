---
sidebar_position: 4
title: Pi coding agent
---

# Pi coding agent settings

Pi is configured from yarn-managed packages plus readonly chezmoi sources under `home/dot_pi/agent/`. The page covers the installed packages, profile-specific settings and models, the shared MCP registry path, and the `APPEND_SYSTEM.md` operating layer that gives Pi the same working rules other harnesses receive.

## Mental model

| Piece             | Source                                                                                                                                                                                                                                                                                             | Target / effect                                                 |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Pi packages       | [`home/readonly_dot_default-yarn-pkgs`](../../../../home/readonly_dot_default-yarn-pkgs)                                                                                                                                                                                                           | yarn globals used by Pi                                         |
| Settings + models | [`home/dot_pi/agent/readonly_settings.{work,personal}.json`](../../../../home/dot_pi/agent/) + work/shared [`readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json) or personal [`readonly_models.personal.json`](../../../../home/dot_pi/agent/readonly_models.personal.json) | `~/.pi/agent/`                                                  |
| MCP servers       | [`home/.chezmoidata/mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml)                                                                                                                                                                                                             | `~/.pi/agent/mcp.json`                                          |
| System prompt     | [`home/dot_pi/agent/readonly_APPEND_SYSTEM.md`](../../../../home/dot_pi/agent/readonly_APPEND_SYSTEM.md)                                                                                                                                                                                           | `~/.pi/agent/APPEND_SYSTEM.md`, appended to Pi's default prompt |

## Using it

### Installed packages

Pi globals are installed via yarn from [`home/readonly_dot_default-yarn-pkgs`](../../../../home/readonly_dot_default-yarn-pkgs) to `~/.default-yarn-pkgs`.

| Package                           | Purpose                                                    |
| --------------------------------- | ---------------------------------------------------------- |
| `@earendil-works/pi-coding-agent` | Core Pi agent                                              |
| `@earendil-works/pi-tui`          | Pi TUI (work profile)                                      |
| `pi-mcp-adapter`                  | MCP adapter extension                                      |
| `pi-subagents`                    | Subagent delegation extension (parallel, isolated context) |

### Profile defaults

| Profile  | Default                                    | Extra providers/models  |
| -------- | ------------------------------------------ | ----------------------- |
| work     | `openrouter` / `anthropic/claude-opus-4.8` | configured work models  |
| personal | `openrouter` / `anthropic/claude-opus-4.8` | `cloudflare-workers-ai` |

Personal Cloudflare uses `CLOUDFLARE_WORKERS_AI_ACCOUNT_ID` and `CLOUDFLARE_WORKERS_AI_API_KEY`. Selectable models include `@cf/zai-org/glm-5.2` and `@cf/moonshotai/kimi-k2.7-code`.

The work-profile LiteLLM provider, the personal Cloudflare Workers AI provider, and the local llama.cpp provider for Pi are covered in [Model registry & routing](../model-registry.md) and [llama.cpp local inference](../llama-cpp/index.md).

### Shared settings

| Setting area       | Behavior                                                                                                                                                              |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Context compaction | Automatic context compaction uses a hybrid sliding window.                                                                                                            |
| Retries            | Exponential backoff retries.                                                                                                                                          |
| Extension loading  | Pi loads `pi-skills`, `pi-mcp-adapter`, and `pi-subagents` from yarn global `node_modules` paths in Pi settings `packages`.                                           |
| Delegation         | `pi-subagents` adds a `subagent` tool so Pi can delegate work to child agents with isolated context windows.                                                          |
| PATH               | Shell PATH order keeps `~/.yarn/bin` ahead of runtime-manager shims so `pi` resolves to the yarn-managed binary.                                                      |
| Secrets            | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `OPENROUTER_API_KEY` are picked up from environment variables exported via `pass` in `config.fish.tmpl`. |

Automatic context compaction triggers when context exceeds `contextWindow − reserveTokens` (16384), keeps the most recent `keepRecentTokens` (80000) verbatim, and LLM-summarizes older turns. It merges iteratively with the prior summary so it never decays into a summary-of-a-summary.

`keepRecentTokens` is raised from Pi's `20000` default to preserve far more high-fidelity recent context before any lossy summarization. The setting is global, not per-model.

`80000` is sized for the smallest window in play: the local Qwen3.6 model at 262144 tokens, ~30% recent-verbatim. It stays comfortably safe on the larger OpenRouter default `anthropic/claude-opus-4.8` with a 1000000-token window.

Pi loads packages from yarn global `node_modules` paths to avoid Pi-managed npm update prompts; `pi install` is not used. Each package's `package.json` `pi` field declares its extension/skills/prompts, which Pi auto-loads.

`pi-skills` exposes `~/.agents/skills/` to Pi; see [Cross-agent memory](../knowledge-base/cross-agent-memory.md). `@earendil-works/pi-tui` stays yarn-managed but is not loaded as a Pi extension package.

The `subagent` tool supports review, scout, and parallel audits while keeping the parent session's token use bounded on long tasks. It is fully local: no network/telemetry beyond the model calls the child agents make.

## Harness operating layer (`APPEND_SYSTEM.md`)

Pi's built-in default prompt is minimal: persona, tools list, "be concise", and "show file paths". Cursor injects a thicker operating layer: tool policy, task/todo discipline, code citations, proactiveness, and edit-scope rules.

`~/.pi/agent/APPEND_SYSTEM.md` closes that gap.

Prompt order:

```text
Pi default -> operating layer -> project context
```

Pi discovers `APPEND_SYSTEM.md` through `DefaultResourceLoader` and appends it before the `<project_context>` block that wraps `AGENTS.md` / `CLAUDE.md`.

Why `APPEND_SYSTEM.md`, not `SYSTEM.md`:

- additive file preserves Pi's default tools list and self-doc pointers.
- replacement file would lose those defaults.
- source is profile-agnostic and installed readonly.

**Scope:** this is harness parity, not a replacement for `AGENTS.md`.

Ported mechanics are the set difference:

```text
Cursor built-in prompt - Pi built-in prompt
```

Included mechanics:

- tone/style: no emojis, no colon before a tool call, backtick paths/symbols.
- tool calling: use dedicated file tools, parallelize independent calls, don't name tools to the user.
- code changes: read before edit, fix introduced linter errors, avoid narrating comments.
- autonomy: finish before yielding.
- task management: todos for complex tasks.
- structured enumerated questions.
- `file_path:line_number` citations.

Excluded Cursor-only mechanics:

- `@`-mentions and system-tag handling.
- terminal-files convention.
- Plan/Agent mode selection.
- Cursor's `start:end:path` citation UI.
- inline line-number disambiguation, because Pi's read tool returns raw text without `LINE|` prefixes.

The read-tool detail was verified in `core/tools/read.ts`; there is no line-prefix stream for the inline-number rule to disambiguate.

Where project context overlaps, `AGENTS.md` wins.
