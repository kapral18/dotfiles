---
title: Tool Configs
---

# Tool Configs

Per-assistant config is generated from a small set of source registries and profile-specific files. MCP servers and model lists stay single-sourced in [MCP servers](../mcp.md) and [Model registry & routing](../model-registry.md).

| Navigation slice                                    | Owns                                                                                 |
| --------------------------------------------------- | ------------------------------------------------------------------------------------ |
| [Launcher defaults](#launcher-defaults)             | Startup models, effort, context, and a short purpose for every launcher              |
| [Cursor and prompt wrap](cursor-and-prompt-wrap.md) | `agent` alias, tmux `Alt-Enter` verification prefix, growth-gated re-injection paths |
| [Profile-based merging](profile-merging.md)         | `.work` / `.personal` sources and `run_onchange` merge scripts                       |
| [Claude and Antigravity](claude-gemini.md)          | Claude settings plus Antigravity rules, hooks, skills, and MCP                       |
| [Pi coding agent](pi.md)                            | Pi packages, settings/models, APPEND_SYSTEM parity layer                             |
| [Other harnesses](other-harnesses.md)               | Codex, OpenCode, tuicr, lgtm, secrets                                                |

## Launcher defaults

Snapshot: **2026-09-11**, on the work machine (`isWork=true`), without command-line, environment, or resumed-session overrides.
These are configured startup selections, not proof that every backend accepts the model.
`—` means no explicit context override; numeric context values are tokens, not output limits.

| Launcher              | What it does                                                                                  | Default model                                         | Effort / thinking                           | Context       |
| --------------------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------- | ------------- |
| `codex`               | OpenAI's native CLI runs coding sessions without the managed local-model catalog injection.   | `gpt-6-sol`                                           | high                                        | short         |
| `,codex`              | The managed wrapper injects metadata for selected local models before launching native Codex. | `gpt-6-sol`                                           | high                                        | short         |
| `,ai codex`           | The unified launcher selects `,codex` while preserving its default model and effort.          | `gpt-6-sol`                                           | high                                        | short         |
| `,codex-openrouter`   | This wrapper runs Codex through OpenRouter's Responses endpoint.                              | `z-ai/glm-5.3-flash`                                  | high                                        | long          |
| `,codex-llama-cpp`    | This wrapper runs Codex against the local llama.cpp server.                                   | `nemotron-3.5`                                        | client high; server auto                    | 262,144       |
| `claude`              | Anthropic's native terminal coding agent reads, edits, and runs project code.                 | `claude-opus-5-5[1m]`                                 | high; thinking always on                    | long          |
| `,ai claude`          | The unified launcher selects native Claude Code without replacing its model or effort.        | `claude-opus-5-5[1m]`                                 | high; thinking always on                    | long          |
| `,claude-codex`       | This wrapper runs Claude Code through the Codex subscription adapter.                         | `gpt-6-sol`                                           | inherits Claude high; frontend thinking off | Codex-derived |
| `,claude-openrouter`  | This wrapper runs Claude Code through OpenRouter's Messages endpoint.                         | `z-ai/glm-5.3-flash`                                  | high; frontend thinking off                 | long          |
| `,claude-llama-cpp`   | This wrapper runs Claude Code against the local llama.cpp server.                             | `nemotron-3.5`                                        | client high; server auto                    | 262,144       |
| `cursor-agent`        | Cursor's native CLI starts sessions without the managed prelaunch MCP token refresh.          | `claude-fable-5.1-high`                               | high; thinking off                          | short         |
| `agent`               | This Fish shortcut forwards arguments to `,cursor`, including its MCP token checks.           | `claude-fable-5.1-high`                               | high; thinking off                          | short         |
| `,cursor`             | The managed wrapper checks MCP tokens and refreshes them when required before sessions.       | `claude-fable-5.1-high`                               | high; thinking off                          | short         |
| `,ai cursor`          | The unified launcher selects `,cursor`, retaining its prelaunch MCP token checks.             | `claude-fable-5.1-high`                               | high; thinking off                          | short         |
| `,cursor-codex`       | This wrapper runs Cursor's local-agent frontend through the Codex subscription adapter.       | `gpt-6-sol`                                           | frontend-controlled; unpinned               | Codex-derived |
| `,cursor-openrouter`  | This wrapper runs Cursor's local-agent frontend through the OpenRouter shim.                  | `z-ai/glm-5.3-flash`                                  | high                                        | long          |
| `,cursor-llama-cpp`   | This wrapper runs Cursor's local-agent frontend against the local llama.cpp server.           | `nemotron-3.5`                                        | server auto                                 | 262,144       |
| `opencode`            | OpenCode runs a primary coding agent with configured worker agents.                           | `openrouter/z-ai/glm-5.3-flash@preset/glm-lanes-high` | high; agent `main`                          | long          |
| `,ai opencode`        | The unified launcher selects native OpenCode without replacing its configured agent or model. | `openrouter/z-ai/glm-5.3-flash@preset/glm-lanes-high` | high; agent `main`                          | long          |
| `,opencode-llama-cpp` | This wrapper selects the local llama.cpp provider for OpenCode.                               | `llama-cpp/nemotron-3.5`                              | server auto                                 | 262,144       |
| `pi`                  | Pi provides a terminal coding agent with the shared extension setup.                          | `openrouter/meta/muse-spark-1.3`                      | xhigh                                       | long          |
| `,ai pi`              | The unified launcher starts Pi while inheriting its native configured defaults.               | `openrouter/meta/muse-spark-1.3`                      | xhigh                                       | long          |
| `omp`                 | Oh My Pi provides a coding agent with built-in task and workflow tools.                       | `anthropic/claude-fable-5.1`                          | high                                        | long          |
| `agy`                 | Google's Antigravity CLI provides a terminal interface for coding tasks.                      | Gemini 3.8 Flash                                      | high                                        | long          |
| `,ai gemini`          | The unified launcher starts Antigravity from the `antigravity` category selection.            | `gemini-3.8-flash`                                    | high                                        | long          |
| `crush`               | Crush provides a terminal coding assistant using its saved provider and model.                | `openrouter/z-ai/glm-5.3-flash`                       | high                                        | long          |
| `freebuff`            | Freebuff provides a terminal coding assistant without a CLI model selector.                   | Not exposed by CLI                                    | Not exposed                                 | Not exposed   |
| `,q`                  | This one-shot Pi launcher answers prompts with tools and brief system guidance.               | `openrouter/deepseek/deepseek-v4.1-flash`             | high                                        | long          |

### Selection notes

- Native-command rows refer to the executables: interactive [Fish functions](../../../../home/dot_config/fish/readonly_config.fish.tmpl) forward bare `codex` and `cursor-agent` to their comma wrappers; `command codex` and `command cursor-agent` bypass those functions.
- Equal model defaults do not make launchers equivalent: [`,codex`](../../../../home/exact_lib/exact_,codex/main.py) adds local-model metadata and [`,cursor`](../../../../home/exact_bin/executable_,cursor) performs prelaunch MCP token checks.
- The `,ai` routes for Cursor, Claude, Codex, and OpenCode inherit their selected launcher's defaults; the default `balanced` depth does not force medium effort.
- Native Claude selects the explicit long-context `claude-opus-5-5[1m]` model at high effort; Opus 5.5 thinking is always on, so effort is the only depth control. Local llama.cpp settings also pin their selected model IDs to `high`, while retaining their local context windows.
- Antigravity's repo policy declares **Gemini 3.8 Flash (High)** for the native TUI, while `,ai gemini` reads the matching Flash/high/long session row from the generated session projection.
- Crush's source `crushrc` pins the large model to `openrouter/z-ai/glm-5.3-flash` at high effort; Crush's runtime data JSON takes precedence and is reconciled separately.
- The three `*-openrouter` wrappers append `@preset/effort-high` to their default model IDs and default to `long`; explicit `--context short` retains the pricing/context-limited route.
- Codex-backed wrappers inherit the model from Codex config but preserve frontend-generated effort; their context budgets come from Codex metadata, with Claude also respecting the smallest reachable child-model budget.
- Local wrappers do not pin backend effort; `server auto` refers to llama.cpp's `reasoning=auto`, not a guarantee of thinking output, and Claude's local frontend keeps thinking off with explicit model-scoped `high` effort.
- Native Cursor's four rows remain pending the user's short-versus-official-1M selector decision; their current source selection is intentionally unchanged.

### Selection sources

The [launcher scripts](../../../../home/exact_bin/), [Codex subscription adapter](../../../../home/exact_lib/exact_,codex-adapter/main.py), [unified launcher](../../../../home/exact_lib/exact_,ai/main.py), and [one-shot launcher](../../../../home/exact_lib/exact_,q/main.py) own wrapper selections.
Native selections come from [Codex](../../../../home/dot_codex/private_config.work.toml), [Claude](../../../../home/dot_claude/settings.work.json), [OpenCode](../../../../home/dot_config/opencode/readonly_opencode.work.jsonc), [Pi](../../../../home/dot_pi/agent/readonly_settings.work.json), and [OMP](../../../../home/dot_omp/private_agent/readonly_config.yml.tmpl) config, plus the live overrides noted above.
Local capacities come from the [llama.cpp router config](../../../../home/dot_config/llama.cpp/models.ini.tmpl); Codex's native window comes from `~/.codex/models_cache.json`.
Cursor's observed catalog offers the official `claude-fable-5-1-high` only as a 1M selector; the requested short-context native Cursor choice is pending. Freebuff's CLI help exposes no model, effort, or context selector.

## Source model

| Concern                | Source of truth                                                                        |
| ---------------------- | -------------------------------------------------------------------------------------- |
| MCP servers            | [`home/.chezmoidata/mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) |
| Model registry         | [`home/.chezmoidata/ai_models/`](../../../../home/.chezmoidata/ai_models)              |
| Profile merges         | explicit `.work.*` / `.personal.*` files plus merge hooks                              |
| Shared operating rules | `~/AGENTS.md` symlink fan-out plus `~/.agents/skills/`                                 |

## Related

- [MCP servers](../mcp.md) — single-sourced server registry
- [Model registry & routing](../model-registry.md) — single-sourced model definitions
- [llama.cpp local inference](../llama-cpp/index.md) — local backend + launchers
- [The Agentic Operating System](../index.md) — governance layer
