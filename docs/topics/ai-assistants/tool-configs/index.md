---
title: Tool Configs
---

# Tool Configs

Each harness keeps a basic config set directly in its own files: model, effort, permissions, and MCP servers.
MCP servers are single-sourced in [MCP servers](../mcp.md); models are set per harness, with no shared registry.

| Page                                        | Owns                                                            |
| ------------------------------------------- | --------------------------------------------------------------- |
| [Profile-based merging](profile-merging.md) | `.work` / `.personal` sources and `run_onchange` merge scripts  |
| [Claude and Antigravity](claude-gemini.md)  | Claude Code settings and subagent profile; Antigravity settings |
| [Pi coding agent](pi.md)                    | Pi packages, settings, models, extensions, `APPEND_SYSTEM.md`   |
| [Other harnesses](other-harnesses.md)       | Codex, OpenCode, OMP, Crush, tuicr, lgtm, secrets               |

## Launcher defaults

Work machine (`isWork=true`), no command-line, environment, or resumed-session overrides.
`—` means no explicit context override; numbers are context tokens.

| Launcher              | What it does                                                                        | Default model                                         | Effort                   | Context |
| --------------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------- | ------------------------ | ------- |
| `claude`              | Claude Code                                                                         | `claude-sonnet-5-5`                                   | high                     | long    |
| `,claude-openrouter`  | Claude Code through OpenRouter's Messages endpoint                                  | `xiaomi/mimo-v2.6-pro`                                | high (preset)            | long    |
| `,claude-llama-cpp`   | Claude Code against the local llama.cpp server                                      | `nemotron-3.5`                                        | client high; server auto | 262,144 |
| `codex` / `,codex`    | Codex; interactive `codex` routes through `,codex`, which adds local-model metadata | `gpt-6.1-sol`                                         | high                     | short   |
| `,codex-openrouter`   | Codex through OpenRouter's Responses endpoint                                       | `xiaomi/mimo-v2.6-pro`                                | high (preset)            | long    |
| `,codex-llama-cpp`    | Codex against the local llama.cpp server                                            | `nemotron-3.5`                                        | client high; server auto | 262,144 |
| `pi`                  | Pi                                                                                  | `openai-codex/gpt-6.1-sol`                            | high                     | short   |
| `omp`                 | Oh My Pi                                                                            | `openai-codex/gpt-6.1-sol`                            | high                     | long    |
| `opencode`            | OpenCode                                                                            | `openrouter/z-ai/glm-5.3-flash@preset/glm-lanes-high` | high                     | long    |
| `,opencode-llama-cpp` | OpenCode with the local llama.cpp provider                                          | `llama-cpp/nemotron-3.5`                              | server auto              | 262,144 |
| `agy`                 | Antigravity CLI                                                                     | Gemini 3.8 Flash                                      | high                     | long    |
| `crush`               | Crush                                                                               | `openrouter/z-ai/glm-5.3-flash`                       | high                     | long    |
| `freebuff`            | Freebuff                                                                            | not exposed by CLI                                    | —                        | —       |
| `,q`                  | one-shot Pi with tools and a short system prompt                                    | `openrouter/deepseek/deepseek-v4.1-flash`             | high                     | long    |

- `command codex` bypasses the fish function that routes `codex` to `,codex`.
- OpenRouter wrappers append `@preset/effort-<level>`; `--context short` keeps the cheaper context tier.
- Local wrappers do not pin backend effort; `server auto` is llama.cpp's `reasoning=auto`.
- Crush's runtime data JSON takes precedence over `crushrc` at runtime.

Sources: [`home/exact_bin/`](../../../../home/exact_bin/) wrappers, [`,q`](../../../../home/exact_lib/exact_,q/main.py), [Codex](../../../../home/dot_codex/private_config.work.toml), [Claude](../../../../home/dot_claude/settings.work.json), [OpenCode](../../../../home/dot_config/opencode/readonly_opencode.work.jsonc), [Pi](../../../../home/dot_pi/agent/readonly_settings.work.json), [OMP](../../../../home/dot_omp/private_agent/readonly_config.yml.tmpl), [llama.cpp router](../../../../home/dot_config/llama.cpp/models.ini.tmpl).
