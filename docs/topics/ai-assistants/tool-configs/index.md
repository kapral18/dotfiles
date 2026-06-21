---
title: Tool Configs
---

# Tool Configs

Per-assistant config is generated from a small set of source registries and profile-specific files. MCP servers and model lists stay single-sourced in [MCP servers](../mcp.md) and [Model registry & routing](../model-registry.md).

| Navigation slice                                    | Owns                                                                 |
| --------------------------------------------------- | -------------------------------------------------------------------- |
| [Cursor and prompt wrap](cursor-and-prompt-wrap.md) | `agent` alias, tmux `Alt-Enter` verification prefix, injection paths |
| [Profile-based merging](profile-merging.md)         | `.work` / `.personal` sources and `run_onchange` merge scripts       |
| [Claude and Gemini](claude-gemini.md)               | Claude settings, LetsFG decision, Gemini settings/MCP injection      |
| [Pi coding agent](pi.md)                            | Pi packages, settings/models, APPEND_SYSTEM parity layer             |
| [Other harnesses](other-harnesses.md)               | Codex, OpenCode, Amp, Copilot, RTK, secrets                          |

## Source model

| Concern                | Source of truth                                                                        |
| ---------------------- | -------------------------------------------------------------------------------------- |
| MCP servers            | [`home/.chezmoidata/mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) |
| Model registry         | [`home/.chezmoidata/ai_models.yaml`](../../../../home/.chezmoidata/ai_models.yaml)     |
| Profile merges         | explicit `.work.*` / `.personal.*` files plus merge hooks                              |
| Shared operating rules | `~/AGENTS.md` symlink fan-out plus `~/.agents/skills/`                                 |

## Related

- [MCP servers](../mcp.md) — single-sourced server registry
- [Model registry & routing](../model-registry.md) — single-sourced model definitions
- [llama.cpp local inference](../llama-cpp/index.md) — local backend + launchers
- [RTK token optimization](../rtk.md) — output compaction and recovery contract
- [The Agentic Operating System](../index.md) — governance layer
