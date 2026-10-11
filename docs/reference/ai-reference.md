---
sidebar_position: 4
---

# AI reference

## Instructions + skills

See [AI assistants](../topics/ai-assistants/index.md) and [Instructions](../topics/ai-assistants/instructions.md).

| Component              | Source path                                                                                    |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| Global instructions    | [`home/readonly_AGENTS.md`](../../home/readonly_AGENTS.md)                                     |
| Skills                 | [`home/exact_dot_agents/exact_skills/`](../../home/exact_dot_agents/exact_skills/)             |
| Shared reviewer prompt | [`home/.chezmoitemplates/reviewer-prompt.md`](../../home/.chezmoitemplates/reviewer-prompt.md) |

`~/CLAUDE.md` imports `@AGENTS.md`; `~/.claude/CLAUDE.md` links to `~/AGENTS.md`. Pi, OMP, Codex, OpenCode, and Antigravity read `~/AGENTS.md` through `symlink_AGENTS.md` entries in their config dirs. There are no hooks.

## Harness configs

Per-tool config sources and the `run_onchange_after_07-*` hooks that render them. See [Tool configs](../topics/ai-assistants/tool-configs/index.md).

| Tool        | Source                                                         | Merge hook                                                                                                                                        |
| ----------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claude Code | [`home/dot_claude/`](../../home/dot_claude/)                   | [`run_onchange_after_07-merge-claude-code-settings.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-claude-code-settings.sh.tmpl) |
| Codex       | [`home/dot_codex/`](../../home/dot_codex/)                     | [`run_onchange_after_07-merge-codex-config.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-codex-config.sh.tmpl)                 |
| Antigravity | [`home/dot_gemini/`](../../home/dot_gemini/)                   | [`run_onchange_after_07-generate-mcp-configs.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl)             |
| OpenCode    | [`home/dot_config/opencode/`](../../home/dot_config/opencode/) | [`run_onchange_after_07-merge-opencode-config.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-opencode-config.sh.tmpl)           |
| Pi          | [`home/dot_pi/agent/`](../../home/dot_pi/agent/)               | [`run_onchange_after_07-merge-pi-config.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-pi-config.sh.tmpl)                       |

## MCP

Canonical MCP registry plus generator/injectors. See [MCP servers](../topics/ai-assistants/mcp.md).

| Component         | Source path                                                                                                                           |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| MCP registry      | [`home/.chezmoidata/mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml)                                                      |
| Registry reader   | [`scripts/mcp_registry.py`](../../scripts/mcp_registry.py)                                                                            |
| Config generator  | [`scripts/generate_mcp_configs.py`](../../scripts/generate_mcp_configs.py)                                                            |
| Codex injector    | [`scripts/inject_mcp_into_codex_toml.py`](../../scripts/inject_mcp_into_codex_toml.py)                                                |
| OpenCode injector | [`scripts/inject_mcp_into_opencode_jsonc.py`](../../scripts/inject_mcp_into_opencode_jsonc.py)                                        |
| Claude MCP merge  | [`scripts/merge_claude_mcp.py`](../../scripts/merge_claude_mcp.py)                                                                    |
| Generate hook     | [`run_onchange_after_07-generate-mcp-configs.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl) |

## Memory and handoffs

On-demand CLIs only. See [Memory and handoffs](../topics/ai-assistants/memory-and-handoffs.md).

| Component                       | Source path                                                                                                                |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Knowledge base (`,ai-kb`)       | [`home/exact_bin/executable_,ai-kb`](../../home/exact_bin/executable_,ai-kb), [`scripts/ai_kb.py`](../../scripts/ai_kb.py) |
| Session handoffs (`,handoff`)   | [`home/exact_bin/executable_,handoff`](../../home/exact_bin/executable_,handoff)                                           |
| Behavior maps (`,behavior-map`) | [`home/exact_lib/exact_,behavior-map/main.py`](../../home/exact_lib/exact_,behavior-map/main.py)                           |
| Embedding service               | [`scripts/embed.py`](../../scripts/embed.py), [`scripts/embed_runner.py`](../../scripts/embed_runner.py)                   |
| Vector retrieval                | [`scripts/vec_runner.py`](../../scripts/vec_runner.py)                                                                     |

## Local inference

See [llama.cpp local inference](../topics/ai-assistants/llama-cpp/index.md).

| Component           | Source path                                                                                                                                                                                                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| GGUF model manifest | [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../home/readonly_dot_default-llama-cpp-models.tmpl)                                                                                                                                                         |
| Router preset       | [`home/dot_config/llama.cpp/models.ini.tmpl`](../../home/dot_config/llama.cpp/models.ini.tmpl)                                                                                                                                                                     |
| Sync hook + helper  | [`run_onchange_after_07-sync-llama-cpp-models.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl), [`scripts/sync_llama_cpp_models.py`](../../scripts/sync_llama_cpp_models.py)                                              |
| Control plane       | [`home/exact_bin/executable_,llama-cpp`](../../home/exact_bin/executable_,llama-cpp)                                                                                                                                                                               |
| Claude launcher     | [`home/exact_bin/executable_,claude-llama-cpp`](../../home/exact_bin/executable_,claude-llama-cpp)                                                                                                                                                                 |
| Codex launcher      | [`home/exact_bin/executable_,codex-llama-cpp`](../../home/exact_bin/executable_,codex-llama-cpp), [`home/exact_bin/executable_,codex`](../../home/exact_bin/executable_,codex), [`home/exact_lib/exact_,codex/main.py`](../../home/exact_lib/exact_,codex/main.py) |
| OpenCode launcher   | [`home/exact_bin/executable_,opencode-llama-cpp`](../../home/exact_bin/executable_,opencode-llama-cpp)                                                                                                                                                             |
| Pi provider         | [`home/dot_pi/agent/readonly_models.json`](../../home/dot_pi/agent/readonly_models.json)                                                                                                                                                                           |
