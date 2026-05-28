---
sidebar_position: 6
---

# Model Registry & Routing

LiteLLM/Azure model definitions are declared once in a canonical YAML; per-tool model lists (Pi, OpenCode) are generated from it. This is the model-side counterpart to the [MCP registry](mcp.md).

Use when adding a model, changing reasoning/cost metadata, or understanding how a model reaches Pi/OpenCode and the local Ollama models.

## Registry: `ai_models.yaml`

Source of truth: [`home/.chezmoidata/ai_models.yaml`](../../../home/.chezmoidata/ai_models.yaml). It holds two sections — `litellm_models` and `azure_models` — each a list of model dicts:

| Field             | Purpose                                                          |
| ----------------- | ---------------------------------------------------------------- |
| `id`              | Provider-qualified model id (e.g. `llm-gateway/claude-opus-4-7`) |
| `name`            | Human-readable display label                                     |
| `reasoning`       | Whether the model supports a thinking/reasoning budget           |
| `thinkingBudgets` | Named token budgets (`minimal`/`low`/`medium`/`high`/`xhigh`)    |
| `contextWindow`   | Max context tokens                                               |
| `maxTokens`       | Max output tokens                                                |
| `cost`            | Per-model `input`/`output`/`cacheRead`/`cacheWrite` pricing      |

[`scripts/ai_models.py`](../../../scripts/ai_models.py) parses these sections (dependency-free), and [`scripts/model_display.py`](../../../scripts/model_display.py) builds the shared display-name format (`<name> [reasoning-emoji] [(cost)] (LiteLLM)`).

## Generators

| Generator                                                                                 | Output                                                                            |
| ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| [`scripts/generate_pi_models.py`](../../../scripts/generate_pi_models.py)                 | Builds Pi `models.json` from a shared base plus work-only LiteLLM/Azure providers |
| [`scripts/merge_opencode_models.py`](../../../scripts/merge_opencode_models.py)           | Merges LiteLLM/Azure models into the OpenCode JSONC config                        |
| [`scripts/probe_litellm_prompt_cache.py`](../../../scripts/probe_litellm_prompt_cache.py) | Diagnostic: probes prompt-cache signals across LiteLLM models                     |

These run inside the per-tool merge hooks (`run_onchange_after_07-merge-pi-config.sh.tmpl`, `run_onchange_after_07-merge-opencode-config.sh.tmpl`). See [Tool configs](tool-configs.md).

## LiteLLM integration (work profile)

Fish exports these values from `pass` when the entries exist (see [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../home/dot_config/fish/readonly_config.fish.tmpl)):

| Variable            | Pass path           | Notes                      |
| ------------------- | ------------------- | -------------------------- |
| `LITELLM_PROXY_KEY` | `litellm/api/token` | API authentication         |
| `LITELLM_API_BASE`  | `litellm/api/base`  | Normalized to end in `/v1` |

- **OpenCode**: the work config ([`home/dot_config/opencode/readonly_opencode.work.jsonc`](../../../home/dot_config/opencode/readonly_opencode.work.jsonc)) uses Google direct Gemini as the primary default (`google/gemini-3.1-pro-preview-customtools`); additional LiteLLM aliases remain available for explicit selection.
- **Pi**: the work config is rendered by `run_onchange_after_07-merge-pi-config.sh.tmpl` into `~/.pi/agent/`, starting from the shared base and adding work-only LiteLLM/Azure providers.

## Ollama

A hook pulls a small list of Ollama models:

- [`home/.chezmoiscripts/run_onchange_after_05-add-ollama-models.sh`](../../../home/.chezmoiscripts/run_onchange_after_05-add-ollama-models.sh)

Environment tuning for Ollama lives in [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../home/dot_config/fish/readonly_config.fish.tmpl).

```bash
chezmoi apply
ollama list
```

For the larger local-inference backend (llama.cpp, `,llama-cpp`), see [llama.cpp local inference](llama-cpp.md).

## Related

- [MCP servers](mcp.md) — the parallel registry for tool servers
- [Tool configs](tool-configs.md) — per-assistant settings and profile merging
- [llama.cpp local inference](llama-cpp.md) — local GGUF backend
