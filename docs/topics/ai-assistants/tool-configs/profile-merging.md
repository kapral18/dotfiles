---
sidebar_position: 2
title: Profile-based merging
---

# Profile-based file merging

Some tools rewrite their config files at runtime, so chezmoi ignores the on-disk target and a `run_onchange` script writes the correct profile-specific version from the repo source.

Instead of complex templates or comment filters, tool configs use explicit `.work.*` and `.personal.*` files.

Flow:

1. merge script checks the `.isWork` template variable.
2. it picks the correct source file.
3. mixed-ownership targets pass through a typed ownership-aware reconciler.
4. it writes the final destination only when content differs and updates both the generic checksum manifest and the AI effective-state ledger.
5. tool-specific formats stay decoupled.

All merge scripts live under [`home/.chezmoiscripts/`](../../../../home/.chezmoiscripts/) and source [`scripts/chezmoi_lib.sh`](../../../../scripts/chezmoi_lib.sh).

| Tool                           | Source files                                                                                                                                                                                                                                                                                                                            | Target                                                                             | Merge script                                               |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Claude Code settings           | [`home/dot_claude/settings.{work,personal}.json`](../../../../home/dot_claude/)                                                                                                                                                                                                                                                         | `~/.claude/settings.json`                                                          | `run_onchange_after_07-merge-claude-code-settings.sh.tmpl` |
| Gemini settings+MCP            | [`home/dot_gemini/settings.json`](../../../../home/dot_gemini/settings.json) + [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml)                                                                                                                                                                                     | `~/.gemini/settings.json`                                                          | `run_onchange_after_07-merge-gemini-settings.sh.tmpl`      |
| OpenCode config+MCP            | [`home/dot_config/opencode/readonly_opencode.{work,personal}.jsonc`](../../../../home/dot_config/opencode/)                                                                                                                                                                                                                             | `~/.config/opencode/opencode.jsonc`                                                | `run_onchange_after_07-merge-opencode-config.sh.tmpl`      |
| Codex config+MCP               | [`home/dot_codex/private_config.{work,personal}.toml`](../../../../home/dot_codex/)                                                                                                                                                                                                                                                     | `~/.codex/config.toml`                                                             | `run_onchange_after_07-merge-codex-config.sh.tmpl`         |
| Pi settings/models             | [`home/dot_pi/agent/readonly_settings.{work,personal}.json`](../../../../home/dot_pi/agent/) + [`readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json) / [`readonly_models.personal.json`](../../../../home/dot_pi/agent/readonly_models.personal.json)                                                            | `~/.pi/agent/{settings,models}.json`                                               | `run_onchange_after_07-merge-pi-config.sh.tmpl`            |
| Copilot settings+MCP+extension | [`home/private_dot_copilot/settings.json`](../../../../home/private_dot_copilot/settings.json) + [`exact_extensions/exact_agent-memory/readonly_extension.mjs`](../../../../home/private_dot_copilot/exact_extensions/exact_agent-memory/readonly_extension.mjs) + [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) | `~/.copilot/{settings.json,mcp-config.json,extensions/agent-memory/extension.mjs}` | `run_onchange_after_07-merge-copilot-config.sh.tmpl`       |

Pi targets are installed readonly. Codex rebuilds from its profile base and reattaches only MCP approvals, hook trust, valid project trust, and valid TUI counters. Copilot recursively preserves undeclared runtime settings, lets declared policy win, and replaces only `subagents.agents` exactly so stale agents and per-agent overrides cannot survive. MCP-server injection for each tool is covered in [MCP servers](../mcp.md).

## Effective-state trace

Each successful 07-hook write records one schema-v1 artifact row under `~/.local/state/chezmoi/generated_artifacts.v1.json`. The row carries the producer, selected profile, complete repo-local input/transform hashes, target, ownership adapter, expected owned semantic hash, consumer, and a local version probe. The runtime `,copilot` preflight also refreshes only the existing `copilot-mcp` row when its locked render changes the semantic `mcp-config.json` target; a no-op launch does not touch either file.

`,doctor ai` evaluates those rows without changing anything:

- whole-file outputs compare exact bytes
- Claude MCP compares only `mcpServers`
- Copilot settings follow the declared baseline shape and require `subagents.agents` exactness
- Codex ignores only its four explicit runtime-owned buckets
- source/transform changes report stale state until the matching hook runs again

Default output is static. `,doctor ai --live` adds deduplicated local harness probes; it does not apply chezmoi, refresh credentials, or use the network.
