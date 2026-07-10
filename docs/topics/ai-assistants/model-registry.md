---
sidebar_position: 9
---

# Model Registry & Routing

LiteLLM/Azure model definitions are declared once in a canonical YAML; per-tool model lists (Pi, OpenCode) are generated from it. This is the model-side counterpart to the [MCP registry](mcp.md).

Use when adding a model, changing reasoning/cost metadata, or understanding how a model reaches Pi/OpenCode.

## Registry: `ai_models.yaml`

Source of truth: [`home/.chezmoidata/ai_models.yaml`](../../../home/.chezmoidata/ai_models.yaml). It holds three sections — `litellm_models` and `azure_models` (each a list of model dicts), plus `agent_review_models`, the review-lane model registry: per-harness `lanes`/`verifier` values rendered into the `/agent-review` subagent profile frontmatter (the verifier is a different model family than `lanes`, paired by review here rather than inferred at runtime). The model-dict fields:

| Field                     | Purpose                                                          |
| ------------------------- | ---------------------------------------------------------------- |
| `id`                      | Provider-qualified model id (e.g. `llm-gateway/claude-opus-4-7`) |
| `name`                    | Human-readable display label                                     |
| `reasoning`               | Whether the model supports a thinking/reasoning budget           |
| `supportsReasoningEffort` | Whether clients may send an explicit reasoning-effort control    |
| `thinkingBudgets`         | Named token budgets (`minimal`/`low`/`medium`/`high`/`xhigh`)    |
| `contextWindow`           | Max context tokens                                               |
| `maxTokens`               | Max output tokens                                                |
| `cost`                    | Per-model `input`/`output`/`cacheRead`/`cacheWrite` pricing      |

[`scripts/ai_models.py`](../../../scripts/ai_models.py) parses these sections (dependency-free), and [`scripts/model_display.py`](../../../scripts/model_display.py) builds the shared display-name format (`<name> [reasoning-emoji] [(cost)] (LiteLLM)`).

## Generators

| Generator                                                                                 | Output                                                                            |
| ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| [`scripts/generate_pi_models.py`](../../../scripts/generate_pi_models.py)                 | Builds Pi `models.json` from a shared base plus work-only LiteLLM/Azure providers |
| [`scripts/merge_opencode_models.py`](../../../scripts/merge_opencode_models.py)           | Merges LiteLLM/Azure models into the OpenCode JSONC config                        |
| [`scripts/probe_litellm_prompt_cache.py`](../../../scripts/probe_litellm_prompt_cache.py) | Diagnostic: probes prompt-cache signals across LiteLLM models                     |

These run inside the per-tool merge hooks (`run_onchange_after_07-merge-pi-config.sh.tmpl`, `run_onchange_after_07-merge-opencode-config.sh.tmpl`). See [Tool configs](tool-configs/index.md).

The Azure AI-backed GPT-5.5 and GPT-5.6 LiteLLM groups return reasoning output but reject Chat Completions requests that combine function tools with an explicit `reasoning_effort`. Their registry entries therefore set `supportsReasoningEffort: false`: Pi renders `compat.supportsReasoningEffort: false`, while the templated OpenCode plugin [`litellm-compat.ts.tmpl`](../../../home/dot_config/opencode/plugins/litellm-compat.ts.tmpl) renders the same model set, removes the unsupported effort option, and asks LiteLLM to drop unsupported compatibility parameters such as `tool_choice`. This matches `,copilot-litellm`, whose working tool-call payload omits `reasoning_effort`.

Ralph exposes Pi model choices from curated allowlists in [`scripts/ralph.py`](../../../scripts/ralph.py) and [`tools/ralph-tui/internal/state/models.go`](../../../tools/ralph-tui/internal/state/models.go). The LiteLLM fallback in [`__comma_provider_models.fish`](../../../home/dot_config/fish/functions/readonly___comma_provider_models.fish) mirrors the same IDs for shell completion when the live gateway cannot be queried. Keep every hard-coded `llm-gateway/*` mirror in sync with `litellm_models[*].id` when adding or retiring gateway models.

## LiteLLM integration (work profile)

Fish exports these values from `pass` when the entries exist (see [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../home/dot_config/fish/readonly_config.fish.tmpl)):

| Variable            | Pass path           | Notes                      |
| ------------------- | ------------------- | -------------------------- |
| `LITELLM_PROXY_KEY` | `litellm/api/token` | API authentication         |
| `LITELLM_API_BASE`  | `litellm/api/base`  | Normalized to end in `/v1` |

- **OpenCode**: the work config ([`home/dot_config/opencode/readonly_opencode.work.jsonc`](../../../home/dot_config/opencode/readonly_opencode.work.jsonc)) uses Google Vertex Gemini as the primary default (`litellm/google-vertex/gemini-flash-latest`); additional LiteLLM aliases remain available for explicit selection.
- **Pi**: the work config is rendered by `run_onchange_after_07-merge-pi-config.sh.tmpl` into `~/.pi/agent/`, starting from the shared base and adding work-only LiteLLM/Azure providers.

## Local inference

The local-inference backend is llama.cpp via `,llama-cpp`; see [llama.cpp local inference](llama-cpp/index.md).

## Related

- [MCP servers](mcp.md) — the parallel registry for tool servers
- [Tool configs](tool-configs/index.md) — per-assistant settings and profile merging
- [llama.cpp local inference](llama-cpp/index.md) — local GGUF backend
