---
sidebar_position: 4
title: Pi coding agent
---

# Pi coding agent settings

Pi is configured from yarn-managed packages plus readonly chezmoi sources under `home/dot_pi/agent/`. The page covers the installed packages, profile-specific settings and models, the shared MCP registry path, and the `APPEND_SYSTEM.md` operating layer that gives Pi the same working rules other harnesses receive.

## Mental model

| Piece               | Source                                                                                                                                                                                                                                                                                             | Target / effect                                                 |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Pi packages         | [`home/readonly_dot_default-yarn-pkgs`](../../../../home/readonly_dot_default-yarn-pkgs)                                                                                                                                                                                                           | yarn globals used by Pi                                         |
| Settings + models   | [`home/dot_pi/agent/readonly_settings.{work,personal}.json`](../../../../home/dot_pi/agent/) + work/shared [`readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json) or personal [`readonly_models.personal.json`](../../../../home/dot_pi/agent/readonly_models.personal.json) | `~/.pi/agent/`                                                  |
| MCP servers         | [`home/.chezmoidata/mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml)                                                                                                                                                                                                             | `~/.pi/agent/mcp.json`                                          |
| System prompt       | [`home/dot_pi/agent/readonly_APPEND_SYSTEM.md`](../../../../home/dot_pi/agent/readonly_APPEND_SYSTEM.md)                                                                                                                                                                                           | `~/.pi/agent/APPEND_SYSTEM.md`, appended to Pi's default prompt |
| Session diagnostics | [`scripts/analyze_pi_session.py`](../../../../scripts/analyze_pi_session.py)                                                                                                                                                                                                                       | privacy-safe aggregate metrics from one saved Pi v3 session     |

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

| Setting area       | Behavior                                                                                                                                                               |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Context compaction | Automatic context compaction uses a hybrid sliding window.                                                                                                             |
| Cache visibility   | Significant prompt-cache misses appear in the transcript; the footer and `/session` expose Pi's own cache accounting.                                                  |
| Retries            | Exponential backoff retries.                                                                                                                                           |
| Extension loading  | Pi loads the chezmoi-managed runtime extensions plus `pi-mcp-adapter` and `pi-subagents` from yarn global `node_modules`.                                              |
| Native tools       | `runtime-parity.ts` enables `grep`, `find`, and `ls` alongside Pi's default tools unless explicit CLI tool-selection flags override the defaults.                      |
| Delegation         | `pi-subagents` adds `subagent` and `subagent_wait` for isolated child contexts; named review profiles cover reviewer, verifier, live-UI, and findings-audit phases.    |
| Session hooks      | `ai-kb-recall.ts` invokes the shared session-context hook, performs depth-aware per-turn recall/correction injection, and forwards tool results to the shared worklog. |
| Git safety         | `runtime-parity.ts` sends bash calls through the shared commit/push classifier and requires interactive approval for commit or push.                                   |
| PATH               | Shell PATH order keeps `~/.yarn/bin` ahead of runtime-manager shims so `pi` resolves to the yarn-managed binary.                                                       |
| Secrets            | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `OPENROUTER_API_KEY` are picked up from environment variables exported via `pass` in `config.fish.tmpl`.  |

Automatic context compaction triggers when context exceeds `contextWindow − reserveTokens` (16384), keeps the most recent `keepRecentTokens` (80000) verbatim, and LLM-summarizes older turns. It merges iteratively with the prior summary so it never decays into a summary-of-a-summary.

`keepRecentTokens` is raised from Pi's `20000` default to preserve far more high-fidelity recent context before any lossy summarization. The setting is global, not per-model.

`80000` is sized for the smallest window in play: the local Qwen3.6 model at 262144 tokens, ~30% recent-verbatim. It stays comfortably safe on the larger OpenRouter default `anthropic/claude-opus-4.8` with a 1000000-token window.

### Prompt-cache and compaction diagnostics

Both profiles set `showCacheMissNotices: true`. Pi emits a transcript notice only for a significant miss after cache activity has been observed; providers that never report cache counters are not treated as misses. The interactive footer shows the latest cache-hit rate, and `/session` shows cached versus uncached prompt tokens plus cumulative cache re-billing.

The repo does not duplicate Pi's cache-miss algorithm. [`scripts/analyze_pi_session.py`](../../../../scripts/analyze_pi_session.py) adds the offline view Pi lacks:

```bash
python3 scripts/analyze_pi_session.py /path/to/session.jsonl
python3 scripts/analyze_pi_session.py /path/to/session.jsonl \
  --max-compactions 2 \
  --max-reread-ratio 0.25 \
  --min-cache-hit-rate 0.50
```

The analyzer accepts only Pi session format v3. It follows the active `parentId` chain, aggregates assistant token/cache/cost fields, records compaction `tokensBefore`, and compares structured built-in `read` calls after compaction with the compaction's `details.readFiles`. It reports only counts and ratios: prompts, summaries, tool output, and file paths never appear.

`cache.hit_rate` is `null` until a positive provider cache counter is observed. `compaction.reread_ratio` is `null` when no post-compaction reads can be measured, and `read_tracking_complete` shows whether every active-branch compaction exposed default read-file details. Exit status `2` means an explicit threshold failed; malformed input or an unsupported format exits `1`.

Pi loads packages from yarn global `node_modules` paths to avoid Pi-managed npm update prompts; `pi install` is not used. Each package's `package.json` `pi` field declares its extension/skills/prompts, which Pi auto-loads.

The installed Pi discovers `~/.agents/skills/` natively, so no skills bridge package is configured. See [Runtime recall wiring](../knowledge-base/cross-agent-memory.md). `@earendil-works/pi-tui` stays yarn-managed but is not loaded as a Pi extension package.

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
