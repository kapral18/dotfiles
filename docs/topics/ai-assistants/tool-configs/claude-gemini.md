---
sidebar_position: 3
title: Claude and Antigravity
---

# Claude and Antigravity

| Tool        | Source                                                                          | Target                                                                        | MCP servers                             |
| ----------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------- |
| Claude Code | [`home/dot_claude/settings.{work,personal}.json`](../../../../home/dot_claude/) | `~/.claude/settings.json` (whole file)                                        | `~/.claude.json` top-level `mcpServers` |
| Antigravity | [`home/dot_gemini/`](../../../../home/dot_gemini/)                              | `~/.gemini/config/` + policy-merged `~/.gemini/antigravity-cli/settings.json` | `~/.gemini/config/mcp_config.json`      |

## Claude Code settings

| Area             | Value                                                                             |
| ---------------- | --------------------------------------------------------------------------------- |
| Model            | `claude-sonnet-5-5`, `effortLevel: high` (also pinned in `modelSettings`)         |
| Thinking         | `alwaysThinkingEnabled: false`                                                    |
| Permissions      | `defaultMode: bypassPermissions`; dangerous-mode prompt skipped                   |
| Subagent nesting | `env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`                                      |
| Auto-compact     | `autoCompactWindow: 400000`: compaction near 366k instead of near 1M              |
| Auto-memory      | `autoMemoryEnabled: false`; `,ai-kb` is the only durable memory                   |
| Away recap       | `awaySummaryEnabled: false`                                                       |
| Hooks            | none                                                                              |
| Work auth        | native Claude enterprise auth; no `apiKeyHelper` or `ANTHROPIC_BASE_URL` override |

Instructions come from `~/.claude/CLAUDE.md` (symlink to `~/AGENTS.md`); skills from `~/.claude/skills` → `~/.agents/skills`.
The only custom agent is `exact_agents/k-agent-reviewer.md.tmpl` (see [Subagents](../subagents.md)); search uses the built-in `Explore`.
The personal profile also keeps fullscreen mode and push notifications.
`settings.llama-cpp*.json.tmpl` hold the settings `,claude-llama-cpp` passes for local models: model-scoped `high` effort, thinking off.

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

Antigravity (`agy`) reads its global MCP servers from `~/.gemini/config/mcp_config.json`, generated directly from the shared [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) registry by `07-generate-mcp-configs`. Hosted OAuth servers without an Antigravity row in `oauth_by_tool` are omitted.

Instructions and skills live in Antigravity's global customization root: `~/.gemini/config/AGENTS.md` points to `~/AGENTS.md`, while `~/.gemini/config/skills` symlinks to `~/.agents/skills`. There are no Antigravity hooks.

Paid Gemini API quota for Antigravity CLI is declared in [`home/dot_gemini/private_antigravity-cli/readonly_settings.policy.json`](../../../../home/dot_gemini/private_antigravity-cli/readonly_settings.policy.json) and merged into `~/.gemini/antigravity-cli/settings.json` by `07-merge-antigravity-cli-settings` (declared-over-live). Policy owns `modelProvider: "gemini"`, `model: "Gemini 3.8 Flash (High)"`, and `enableTelemetry: false`, and strips any top-level `gcp` pin. That Flash pin is the interactive-TUI default. Runtime fields such as `trustedWorkspaces`, `permissions`, and `statusLine` survive. Fish still loads `GEMINI_API_KEY` from `pass google/gemini/api/token`; the key alone does not switch providers.

Do not export `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, or `GOOGLE_CLOUD_LOCATION` into interactive shells. Those force `authMethod=gcp` onto `aiplatform.googleapis.com` and burn shared Vertex quota instead. Corporate Google OAuth without the Gemini API key provider lands on Antigravity Starter product quota.
