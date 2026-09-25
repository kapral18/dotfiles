---
sidebar_position: 3
title: Claude and Antigravity
---

# Claude and Antigravity

Claude Code and Antigravity use config surfaces backed by the shared MCP registry. Claude keeps runtime-managed fields in `~/.claude.json`, while Antigravity receives native MCP configuration at `~/.gemini/config/mcp_config.json`.

## Mental model

| Tool        | Source                                                                          | Target                                                                                       | Registry path                                                                                                                 |
| ----------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Claude Code | [`home/dot_claude/settings.{work,personal}.json`](../../../../home/dot_claude/) | `~/.claude/settings.json`                                                                    | `~/.claude.json` top-level `mcpServers`                                                                                       |
| Antigravity | [`home/dot_gemini/`](../../../../home/dot_gemini/)                              | `~/.gemini/config/mcp_config.json` + policy-merged `~/.gemini/antigravity-cli/settings.json` | shared [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) + `antigravity-cli/readonly_settings.policy.json` |

## Using it

### Claude Code settings

Claude profile behavior:

| Area                  | Behavior                                                                                                                                                |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Model and context     | `claude-opus-5-5[1m]`; explicit long-context `session_models.claude_code` selector                                                                      |
| Thinking and effort   | `alwaysThinkingEnabled: false`; `effortLevel: high` in both profiles                                                                                    |
| Local llama.cpp       | model-scoped `high` effort with thinking off; local context windows stay unchanged                                                                      |
| Dangerous-mode prompt | skipped in both profiles                                                                                                                                |
| Subagent nesting      | `env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` in every settings profile (nesting off); every `exact_agents/` profile pins `tools:` without `Agent`       |
| Auto-compact window   | `autoCompactWindow: 400000` in both profiles; root sessions and subagents compact near 366k instead of near 1M                                          |
| Auto-memory           | `autoMemoryEnabled: false` in both profiles: Claude Code neither reads nor writes `~/.claude/projects/*/memory`, so `,ai-kb` is the only durable memory |
| Work auth             | native Claude enterprise auth; no `apiKeyHelper` / `ANTHROPIC_BASE_URL` override                                                                        |
| MCP storage           | `~/.claude.json` top-level `mcpServers`                                                                                                                 |
| Merge strategy        | selected profile plus canonical `session_models.claude_code` model and effort                                                                           |

Interactive fish/bash/zsh sessions leave `claude` native. MCP wiring is handled only by the managed registry and apply-time config generation.

### LetsFG

**LetsFG** is intentionally not exposed through the shared MCP registry.

| Decision               | Reason                                                                                                                                      |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| not in MCP registry    | flight tools are irrelevant to most sessions                                                                                                |
| skill-loaded on demand | agents load [`k-letsfg/SKILL.md`](../../../../home/exact_dot_agents/exact_skills/exact_k-letsfg/readonly_SKILL.md) only for travel searches |
| local CLI              | `letsfg` uv tool comes from [`home/readonly_dot_default-uv-tools.tmpl`](../../../../home/readonly_dot_default-uv-tools.tmpl)                |
| normal agent mode      | passes `LETSFG_BROWSERS=0` per invocation                                                                                                   |
| browser connectors     | explicit opt-in                                                                                                                             |

Playwriter remains a fallback for rendered UI checks or booking-adjacent flows that need explicit user confirmation.

### Antigravity settings

Antigravity (`agy`) reads its global MCP servers from `~/.gemini/config/mcp_config.json`, generated directly from the shared [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) registry by `07-generate-mcp-configs`. Hosted servers (`scsi-main`, `slack`) run as `,mcp-token --bridge` stdio servers with per-request bearer token injection from cursor-cli's rotating OAuth caches.

Instructions and skills live in Antigravity's global customization root: `~/.gemini/config/AGENTS.md` points to `~/AGENTS.md`, while `~/.gemini/config/skills` symlinks to `~/.agents/skills`. `~/.gemini/config/hooks.json` injects shared session context on the first `PreInvocation`, carries premise-check nudges from `PreToolUse` into the next invocation, and records `PostToolUse` events.

Paid Gemini API quota for Antigravity CLI is declared in [`home/dot_gemini/antigravity-cli/readonly_settings.policy.json`](../../../../home/dot_gemini/antigravity-cli/readonly_settings.policy.json) and merged into `~/.gemini/antigravity-cli/settings.json` by `07-merge-antigravity-cli-settings` (declared-over-live). Policy owns `modelProvider: "gemini"`, `model: "Gemini 3.8 Flash (High)"`, and `enableTelemetry: false`, and strips any top-level `gcp` pin. That Flash pin is the interactive-TUI default and matches `session_models.antigravity`, so `,ai gemini` passes `gemini-3.8-flash --effort high`. Every Antigravity category uses the Flash base model with its row-specific effort. Dynamic review subagents receive the abstract `flash` tier: `invoke_subagent` accepts only tiers, and every `category_models.antigravity` row is Gemini Flash. Runtime fields such as `trustedWorkspaces`, `permissions`, and `statusLine` survive. Fish still loads `GEMINI_API_KEY` from `pass google/gemini/api/token`; the key alone does not switch providers.

Do not export `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, or `GOOGLE_CLOUD_LOCATION` into interactive shells. Those force `authMethod=gcp` onto `aiplatform.googleapis.com` and burn shared Vertex quota instead. Corporate Google OAuth without the Gemini API key provider lands on Antigravity Starter product quota.

An A/B on 2026-09-25 used 3 tests-first tasks rebuilt from past commits, with 2 repetitions per arm. It tested subagents and main sessions separately. Long implementation subagents cost $15.16 and $15.56 with the window, against $21.90 and $24.94 without it. All tasks passed in every run and no test file was edited. The one main session that compacted also passed every task, at $11.00 against $12.48 for its control run. The `,claude-llama-cpp` additive settings files and the env overrides of other wrappers take precedence over this value.

The personal Claude profile keeps fullscreen mode and push notifications. Both profiles explicitly pin `modelSettings.claude-opus-5-5[1m].effortLevel` to `high`, matching the canonical long-context `session_models.claude_code` row.
