---
sidebar_position: 4
---

# AI reference

Source map for AI governance, harness configs, model/MCP generation, memory, Palantír, and local inference.

## Governance + skills

See [The Agentic Operating System](../topics/ai-assistants/index.md).

| Component                     | Source path                                                                        |
| ----------------------------- | ---------------------------------------------------------------------------------- |
| Assistant SOP (single source) | [`home/readonly_AGENTS.md`](../../home/readonly_AGENTS.md)                         |
| Assistant skills              | [`home/exact_dot_agents/exact_skills/`](../../home/exact_dot_agents/exact_skills/) |
| Shared assistant hooks        | [`home/exact_dot_agents/exact_hooks/`](../../home/exact_dot_agents/exact_hooks/)   |
| Cursor CLI hooks              | [`home/dot_cursor/hooks.json`](../../home/dot_cursor/hooks.json)                   |

`~/CLAUDE.md`, `~/.gemini/GEMINI.md`, `~/.cursor/AGENTS.md`, `~/.codex/AGENTS.md`, `~/.config/opencode/AGENTS.md`, and `~/.copilot/copilot-instructions.md` are symlinks to `~/AGENTS.md`.

## Harness configs

Per-tool config sources and the `run_onchange_after_07-*` hooks that render them. See [Tool configs](../topics/ai-assistants/tool-configs/index.md).

| Tool        | Source                                                         | Merge hook                                                                                                                                        |
| ----------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claude Code | [`home/dot_claude/`](../../home/dot_claude/)                   | [`run_onchange_after_07-merge-claude-code-settings.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-claude-code-settings.sh.tmpl) |
| Codex       | [`home/dot_codex/`](../../home/dot_codex/)                     | [`run_onchange_after_07-merge-codex-config.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-codex-config.sh.tmpl)                 |
| Gemini      | [`home/dot_gemini/`](../../home/dot_gemini/)                   | [`run_onchange_after_07-merge-gemini-settings.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-gemini-settings.sh.tmpl)           |
| OpenCode    | [`home/dot_config/opencode/`](../../home/dot_config/opencode/) | [`run_onchange_after_07-merge-opencode-config.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-opencode-config.sh.tmpl)           |
| Pi          | [`home/dot_pi/agent/`](../../home/dot_pi/agent/)               | [`run_onchange_after_07-merge-pi-config.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-pi-config.sh.tmpl)                       |
| Copilot     | [`home/private_dot_copilot/`](../../home/private_dot_copilot/) | [`run_onchange_after_07-merge-copilot-config.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-copilot-config.sh.tmpl)             |
| Cursor      | [`home/dot_cursor/`](../../home/dot_cursor/)                   | settings tracked directly                                                                                                                         |

## Model registry

Single source of truth for LiteLLM/Azure definitions, curated Cursor models, Pi extras, provider routes, and review-lane model policy; per-tool model configs and the generated mirror derive from it. See [Model registry & routing](../topics/ai-assistants/model-registry.md).

| Component               | Source path                                                                            |
| ----------------------- | -------------------------------------------------------------------------------------- |
| Model definitions       | [`home/.chezmoidata/ai_models.yaml`](../../home/.chezmoidata/ai_models.yaml)           |
| YAML reader             | [`scripts/ai_models.py`](../../scripts/ai_models.py)                                   |
| Pi models generator     | [`scripts/generate_pi_models.py`](../../scripts/generate_pi_models.py)                 |
| OpenCode models merge   | [`scripts/merge_opencode_models.py`](../../scripts/merge_opencode_models.py)           |
| Display-name formatting | [`scripts/model_display.py`](../../scripts/model_display.py)                           |
| Prompt-cache probe      | [`scripts/probe_litellm_prompt_cache.py`](../../scripts/probe_litellm_prompt_cache.py) |
| Pi session analyzer     | [`scripts/analyze_pi_session.py`](../../scripts/analyze_pi_session.py)                 |

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

## Memory

Two distinct memory layers. See [Agent memory](../topics/ai-assistants/knowledge-base/index.md).

| Component                     | Source path                                                                                                                                                      |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AI knowledge base (`,ai-kb`)  | [`home/exact_bin/executable_,ai-kb`](../../home/exact_bin/executable_,ai-kb), [`scripts/ai_kb.py`](../../scripts/ai_kb.py)                                       |
| Proof ledger (`,proof`)       | [`home/exact_bin/executable_,proof`](../../home/exact_bin/executable_,proof), [`home/exact_lib/exact_,proof/main.py`](../../home/exact_lib/exact_,proof/main.py) |
| Embedding service             | [`scripts/embed.py`](../../scripts/embed.py), [`scripts/embed_runner.py`](../../scripts/embed_runner.py)                                                         |
| Vector retrieval              | [`scripts/vec_runner.py`](../../scripts/vec_runner.py)                                                                                                           |
| Hook memory (`,agent-memory`) | [`home/exact_bin/executable_,agent-memory`](../../home/exact_bin/executable_,agent-memory), [`scripts/agent_memory.py`](../../scripts/agent_memory.py)           |

## Palantír orchestrator

See [Palantír orchestrator](../topics/ai-assistants/palantir.md).

| Component             | Source path                                                                                                                                    |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| CLI entry             | [`home/exact_bin/executable_,palantir`](../../home/exact_bin/executable_,palantir)                                                             |
| Deployed core         | [`home/exact_lib/exact_,palantir/`](../../home/exact_lib/exact_,palantir/)                                                                     |
| Role config           | [`home/dot_config/palantir/`](../../home/dot_config/palantir/)                                                                                 |
| Skill                 | [`home/exact_dot_agents/exact_skills/exact_k-palantir/`](../../home/exact_dot_agents/exact_skills/exact_k-palantir/)                           |
| Fish completion       | [`home/dot_config/fish/completions/readonly_,palantir.fish`](../../home/dot_config/fish/completions/readonly_,palantir.fish)                   |
| Tmux dashboard/status | [`home/dot_config/exact_tmux/exact_conf.d/readonly_45-palantir.conf`](../../home/dot_config/exact_tmux/exact_conf.d/readonly_45-palantir.conf) |

## Local inference

See [llama.cpp local inference](../topics/ai-assistants/llama-cpp/index.md).

| Component           | Source path                                                                                                                                                                                                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| GGUF model manifest | [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../home/readonly_dot_default-llama-cpp-models.tmpl)                                                                                                                                                         |
| Router preset       | [`home/dot_config/llama.cpp/models.ini.tmpl`](../../home/dot_config/llama.cpp/models.ini.tmpl)                                                                                                                                                                     |
| Chat template       | [`home/dot_config/llama.cpp/readonly_qwen3.6-chat-template.jinja`](../../home/dot_config/llama.cpp/readonly_qwen3.6-chat-template.jinja)                                                                                                                           |
| Sync hook + helper  | [`run_onchange_after_07-sync-llama-cpp-models.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl), [`scripts/sync_llama_cpp_models.py`](../../scripts/sync_llama_cpp_models.py)                                              |
| Control plane       | [`home/exact_bin/executable_,llama-cpp`](../../home/exact_bin/executable_,llama-cpp)                                                                                                                                                                               |
| Claude launcher     | [`home/exact_bin/executable_,claude-llama-cpp`](../../home/exact_bin/executable_,claude-llama-cpp)                                                                                                                                                                 |
| Codex launcher      | [`home/exact_bin/executable_,codex-llama-cpp`](../../home/exact_bin/executable_,codex-llama-cpp), [`home/exact_bin/executable_,codex`](../../home/exact_bin/executable_,codex), [`home/exact_lib/exact_,codex/main.py`](../../home/exact_lib/exact_,codex/main.py) |
| OpenCode launcher   | [`home/exact_bin/executable_,opencode-llama-cpp`](../../home/exact_bin/executable_,opencode-llama-cpp)                                                                                                                                                             |
| Pi provider         | [`home/dot_pi/agent/readonly_models.json`](../../home/dot_pi/agent/readonly_models.json)                                                                                                                                                                           |
