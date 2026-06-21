---
sidebar_position: 3
title: Claude and Gemini
---

# Claude and Gemini

## Claude Code settings

Source: [`home/dot_claude/settings.{work,personal}.json`](../../../../home/dot_claude/) → `~/.claude/settings.json`.

Claude profile behavior:

| Area                  | Behavior                                                                         |
| --------------------- | -------------------------------------------------------------------------------- |
| Extended thinking     | enabled in both profiles                                                         |
| Dangerous-mode prompt | skipped in both profiles                                                         |
| Work auth             | native Claude enterprise auth; no `apiKeyHelper` / `ANTHROPIC_BASE_URL` override |
| MCP storage           | `~/.claude.json` top-level `mcpServers`                                          |
| Merge strategy        | update only `mcpServers`, preserve runtime-managed fields                        |

**LetsFG** is intentionally not exposed through the shared MCP registry.

| Decision               | Reason                                                                                                                                  |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| not in MCP registry    | flight tools are irrelevant to most sessions                                                                                            |
| skill-loaded on demand | agents load [`letsfg/SKILL.md`](../../../../home/exact_dot_agents/exact_skills/exact_letsfg/readonly_SKILL.md) only for travel searches |
| local CLI              | `letsfg` uv tool comes from [`home/readonly_dot_default-uv-tools.tmpl`](../../../../home/readonly_dot_default-uv-tools.tmpl)            |
| normal agent mode      | passes `LETSFG_BROWSERS=0` per invocation                                                                                               |
| browser connectors     | explicit opt-in                                                                                                                         |

Playwriter remains a fallback for rendered UI checks or booking-adjacent flows that need explicit user confirmation.

## Gemini CLI settings

Source: [`home/dot_gemini/settings.json`](../../../../home/dot_gemini/settings.json) → `~/.gemini/settings.json`.

- MCP servers are injected from the shared [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) registry at apply time (no longer hardcoded in the settings file).
- Tool approval is controlled by `general.defaultApprovalMode` (we use `auto_edit` to auto-approve edit tools).
