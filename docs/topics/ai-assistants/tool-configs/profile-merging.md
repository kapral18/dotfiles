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
3. it writes the final destination.
4. tool-specific formats stay decoupled.

All merge scripts live under [`home/.chezmoiscripts/`](../../../../home/.chezmoiscripts/) and source [`scripts/chezmoi_lib.sh`](../../../../scripts/chezmoi_lib.sh).

| Tool                       | Source files                                                                                                                                                                                                                                                                 | Target                                                               | Merge script                                               |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ---------------------------------------------------------- |
| Claude Code settings       | [`home/dot_claude/settings.{work,personal}.json`](../../../../home/dot_claude/)                                                                                                                                                                                              | `~/.claude/settings.json`                                            | `run_onchange_after_07-merge-claude-code-settings.sh.tmpl` |
| Gemini settings+MCP        | [`home/dot_gemini/settings.json`](../../../../home/dot_gemini/settings.json) + [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml)                                                                                                                          | `~/.gemini/settings.json`                                            | `run_onchange_after_07-merge-gemini-settings.sh.tmpl`      |
| OpenCode config+MCP        | [`home/dot_config/opencode/readonly_opencode.{work,personal}.jsonc`](../../../../home/dot_config/opencode/)                                                                                                                                                                  | `~/.config/opencode/opencode.jsonc`                                  | `run_onchange_after_07-merge-opencode-config.sh.tmpl`      |
| Codex config+MCP           | [`home/dot_codex/private_config.{work,personal}.toml`](../../../../home/dot_codex/)                                                                                                                                                                                          | `~/.codex/config.toml`                                               | `run_onchange_after_07-merge-codex-config.sh.tmpl`         |
| Pi settings/models         | [`home/dot_pi/agent/readonly_settings.{work,personal}.json`](../../../../home/dot_pi/agent/) + [`readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json) / [`readonly_models.personal.json`](../../../../home/dot_pi/agent/readonly_models.personal.json) | `~/.pi/agent/{settings,models}.json`                                 | `run_onchange_after_07-merge-pi-config.sh.tmpl`            |
| Copilot settings+MCP+hooks | [`home/private_dot_copilot/settings.json`](../../../../home/private_dot_copilot/settings.json) + [`hooks.json`](../../../../home/private_dot_copilot/hooks.json) + [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml)                                      | `~/.copilot/{settings.json,mcp-config.json,hooks/agent-memory.json}` | `run_onchange_after_07-merge-copilot-config.sh.tmpl`       |

Pi targets are installed readonly. MCP-server injection for each tool is covered in [MCP servers](../mcp.md).
