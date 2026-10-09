---
sidebar_position: 4
title: Pi coding agent
---

# Pi coding agent settings

Pi runs from pnpm-managed packages plus readonly chezmoi sources under `home/dot_pi/agent/`.
There are no hooks, advisors, or model-profile switchers; settings and models are set directly in the files below.

## Sources

| Piece             | Source                                                                                                                                                                                | Target                                                                                     |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Packages          | [`home/readonly_dot_default-pnpm-pkgs`](../../../../home/readonly_dot_default-pnpm-pkgs) (`@earendil-works/pi-coding-agent`, `@earendil-works/pi-tui`, `pi-subagents`)                | pnpm globals                                                                               |
| Settings          | [`readonly_settings.{work,personal}.json`](../../../../home/dot_pi/agent/)                                                                                                            | merged into `~/.pi/agent/settings.json` by `run_onchange_after_07-merge-pi-config.sh.tmpl` |
| Models            | [`readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json) (work) or [`readonly_models.personal.json`](../../../../home/dot_pi/agent/readonly_models.personal.json) | merged into `~/.pi/agent/models.json`                                                      |
| MCP servers       | [`home/.chezmoidata/mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml)                                                                                                | `~/.pi/agent/mcp.json`                                                                     |
| Instructions      | `symlink_AGENTS.md` → `~/AGENTS.md`                                                                                                                                                   | Pi project context                                                                         |
| Operating layer   | [`readonly_APPEND_SYSTEM.md`](../../../../home/dot_pi/agent/readonly_APPEND_SYSTEM.md)                                                                                                | appended to Pi's default prompt                                                            |
| Subagent profiles | `exact_agents/k-agent-reviewer.md.tmpl`, `exact_agents/k-agent-scout.md`                                                                                                              | `~/.pi/agent/agents/`                                                                      |
| Extensions        | `exact_extensions/`                                                                                                                                                                   | `~/.pi/agent/extensions/`                                                                  |

## Settings

| Area            | Value                                                                                                                            |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Default model   | `openai-codex` / `gpt-6.1-sol`, thinking `high` (both profiles)                                                                  |
| Extra providers | `openrouter` and `llama-cpp` in `models*.json`; see [llama.cpp](../llama-cpp/index.md)                                           |
| Tools           | `defaultTools: ["+codemode", "+find", "+grep", "+ls"]`                                                                           |
| Compaction      | `reserveTokens` 16384, `keepRecentTokens` 80000 (raised from Pi's 20000 to keep more recent context verbatim)                    |
| Retries         | enabled, `maxRetries` 5                                                                                                          |
| Cache notices   | `showCacheMissNotices: true`; `/session` shows cached vs uncached tokens                                                         |
| Subagents       | `pi-subagents` loaded with empty `skills`/`prompts`; `disableBuiltins: true`, `defaultSubagentContext: "fresh"`, sync by default |
| Secrets         | API keys come from environment variables exported via `pass` in `config.fish.tmpl`                                               |

Pi loads packages from `~/.local/share/pnpm-global-links/node_modules/`, which `,install-pnpm-pkgs` rebuilds after each sync, because pnpm 11+ global paths are hashed.
Pi discovers `~/.agents/skills/` natively.

Pi 1.1.0 loads context by path, not symlink identity. Inside `$HOME`, it includes both `~/.pi/agent/AGENTS.md` and `~/AGENTS.md`. The global link remains necessary for repositories outside `$HOME`.

## Extensions

| File                            | Purpose                                                                                                                                                                                 |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `context-mode.ts.tmpl`          | `/context-mode short\|long\|status`: choose a smaller working window on models with long-context pricing tiers. Shared logic in `~/lib/shared/context_mode.ts` (also used by OMP).      |
| `model-pin.ts`                  | Re-pins the routed model after a turn whose echoed model id differs, so `pi -c` restores it. Workaround for [earendil-works/pi#9243](https://github.com/earendil-works/pi/issues/9243). |
| `read-supersede.ts`             | Replaces older reads of the same file with a short notice before each provider call, only while the cache cost is small.                                                                |
| `subagent/readonly_config.json` | `modelResponseAliases` so `pi-subagents` accepts the `claude-fable-5-1` echo.                                                                                                           |

### Working-context selection

GPT models default to short; other eligible families keep the native window until `/context-mode short`.
A model is eligible only when it has a short window below native capacity (from `cost.tiers[].inputTokensAbove`; GPT without tier data uses 272,000 tokens).
The choice is a session entry: it follows the branch and survives resume.
Switching to short is refused when history already exceeds the short window; run `/compact` first.

## Subagents

Only the repo profiles exist; see [Subagents](../subagents.md).

| Profile            | Model                                                                   | Use                                                     |
| ------------------ | ----------------------------------------------------------------------- | ------------------------------------------------------- |
| `k-agent-scout`    | `openai-codex/gpt-6-luna`, thinking low, read-only tools, fresh context | broad read-only search                                  |
| `k-agent-reviewer` | `gpt-6.1-sol`, high                                                     | a risky finished change, or a review the user asked for |

Both set `maxSubagentDepth: 0`, so they cannot start other agents.

## `APPEND_SYSTEM.md`

Pi's default prompt is minimal. `APPEND_SYSTEM.md` adds tone, tool-calling, codemode, edit, citation, autonomy, and task-list rules.
Order: Pi default → `APPEND_SYSTEM.md` → project context (`AGENTS.md`). Where they overlap, `AGENTS.md` wins.
It is additive rather than `SYSTEM.md` so Pi keeps its default tool list and self-doc pointers.
`,q` skips it by passing a short `--system-prompt` and an empty `--append-system-prompt`.
