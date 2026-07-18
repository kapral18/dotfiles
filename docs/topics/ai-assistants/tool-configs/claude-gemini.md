---
sidebar_position: 3
title: Claude and Gemini
---

# Claude and Gemini

Claude Code and Gemini CLI use small profile/config surfaces backed by the shared MCP registry. Claude keeps runtime-managed fields in `~/.claude.json`, while Gemini receives MCP server injection into its settings at apply time.

## Mental model

| Tool        | Source                                                                          | Target                    | Registry path                                                                                      |
| ----------- | ------------------------------------------------------------------------------- | ------------------------- | -------------------------------------------------------------------------------------------------- |
| Claude Code | [`home/dot_claude/settings.{work,personal}.json`](../../../../home/dot_claude/) | `~/.claude/settings.json` | `~/.claude.json` top-level `mcpServers`                                                            |
| Gemini CLI  | [`home/dot_gemini/settings.json`](../../../../home/dot_gemini/settings.json)    | `~/.gemini/settings.json` | shared [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) injected at apply time |

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

### Gemini CLI settings

MCP servers are injected from the shared [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) registry at apply time. Tool approval is controlled by `general.defaultApprovalMode`; this repo uses `auto_edit` to auto-approve edit tools.
