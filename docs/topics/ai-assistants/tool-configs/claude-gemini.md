---
sidebar_position: 3
title: Claude and Antigravity
---

# Claude and Antigravity

Claude Code and Antigravity use config surfaces backed by the shared MCP registry. Claude keeps runtime-managed fields in `~/.claude.json`, while Antigravity receives native MCP configuration at `~/.gemini/config/mcp_config.json`.

## Mental model

| Tool        | Source                                                                          | Target                             | Registry path                                                                                      |
| ----------- | ------------------------------------------------------------------------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------- |
| Claude Code | [`home/dot_claude/settings.{work,personal}.json`](../../../../home/dot_claude/) | `~/.claude/settings.json`          | `~/.claude.json` top-level `mcpServers`                                                            |
| Antigravity | [`home/dot_gemini/`](../../../../home/dot_gemini/)                              | `~/.gemini/config/mcp_config.json` | shared [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) rendered at apply time |

## Using it

### Claude Code settings

Claude profile behavior:

| Area                  | Behavior                                                                         |
| --------------------- | -------------------------------------------------------------------------------- |
| Thinking and effort   | `alwaysThinkingEnabled: false`; `effortLevel: xhigh` persisted in both profiles  |
| Dangerous-mode prompt | skipped in both profiles                                                         |
| Work auth             | native Claude enterprise auth; no `apiKeyHelper` / `ANTHROPIC_BASE_URL` override |
| MCP storage           | `~/.claude.json` top-level `mcpServers`                                          |
| Merge strategy        | update only `mcpServers`, preserve runtime-managed fields                        |

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

Instructions and skills live in Antigravity's global customization root: `~/.gemini/config/AGENTS.md` points to `~/AGENTS.md`, while `~/.gemini/config/skills` symlinks to `~/.agents/skills`. `~/.gemini/config/hooks.json` injects shared session context on the first `PreInvocation`, carries premise-check nudges from `PreToolUse` into the next invocation, records `PostToolUse` events, and gates `git commit`/`git push`.
