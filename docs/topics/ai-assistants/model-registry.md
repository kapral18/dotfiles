---
sidebar_position: 9
---

# Model Registry & Routing

Canonical model policy stays in the existing YAML and per-harness configs; generated mirrors project that policy into one machine-readable view without becoming a competing source of truth. This is the model-side counterpart to the [MCP registry](mcp.md).

Use when adding a model, changing reasoning/cost metadata, checking live catalog drift, or understanding how a model reaches Pi, OpenCode, Ralph, and provider launchers.

## Registry: `ai_models.yaml`

Source of truth: [`home/.chezmoidata/ai_models.yaml`](../../../home/.chezmoidata/ai_models.yaml). Its sections have distinct policy roles:

| Section               | Canonical policy                                                                                                                |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `litellm_models`      | LiteLLM model definitions rendered into Pi/OpenCode                                                                             |
| `azure_models`        | Azure Foundry model definitions rendered into Pi/OpenCode                                                                       |
| `cursor_models`       | Ralph's curated Cursor aliases; `recommended: true` is the narrower TUI set                                                     |
| `pi_extra_models`     | Non-LiteLLM Pi selectors retained by Ralph                                                                                      |
| `provider_models`     | Static provider-route choices for shell completion                                                                              |
| `agent_review_models` | Per-harness review `lanes`/`verifier` pairs; the verifier-family pairing is reviewed here rather than inferred or auto-promoted |

Recommended Cursor entries use `recommendation_rank` to preserve the deliberate TUI picker order independently of the broader curated registry order.

The LiteLLM/Azure model-dict fields are:

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
| [`scripts/model_mirrors.py`](../../../scripts/model_mirrors.py)                           | Generates/verifies the v1 static mirror and runs explicit live drift probes       |
| [`scripts/probe_litellm_prompt_cache.py`](../../../scripts/probe_litellm_prompt_cache.py) | Diagnostic: probes prompt-cache signals across LiteLLM models                     |

The Pi/OpenCode generators run inside their per-tool merge hooks (`run_onchange_after_07-merge-pi-config.sh.tmpl`, `run_onchange_after_07-merge-opencode-config.sh.tmpl`). The mirror is a committed generated artifact verified by tests and `make check`; diagnostic probes are operator initiated. See [Tool configs](tool-configs/index.md).

The Azure AI-backed GPT-5.5 and GPT-5.6 LiteLLM groups return reasoning output but reject Chat Completions requests that combine function tools with an explicit `reasoning_effort`. Their registry entries therefore set `supportsReasoningEffort: false`: Pi renders `compat.supportsReasoningEffort: false`, while the templated OpenCode plugin [`litellm-compat.ts.tmpl`](../../../home/dot_config/opencode/plugins/litellm-compat.ts.tmpl) renders the same model set, removes the unsupported effort option, and asks LiteLLM to drop unsupported compatibility parameters such as `tool_choice`. This matches `,copilot-litellm`, whose working tool-call payload omits `reasoning_effort`.

## Generated mirror v1

[`home/dot_config/ai/readonly_model-mirrors.v1.json`](../../../home/dot_config/ai/readonly_model-mirrors.v1.json) deploys to `~/.config/ai/model-mirrors.v1.json`. It is generated from the registry, harness configs, Ralph roles, and the versioned installed-harness evidence in [`scripts/model_capabilities.v1.json`](../../../scripts/model_capabilities.v1.json).

Every harness and provider route has three catalogs:

| Catalog       | Meaning                                                                                               |
| ------------- | ----------------------------------------------------------------------------------------------------- |
| `available`   | What fixed installed-source evidence or configured capability data establishes; may be incomplete     |
| `curated`     | Operator-owned IDs allowed by current policy                                                          |
| `recommended` | Deliberate subset shown as preferred choices; availability alone never promotes a model into this set |

Each catalog carries `status`, `models`, `complete`, `reason`, and `provenance`. Status is `known`, `unknown`, or `error`; `unknown`/`error` catalogs must have no models, `complete: null`, and a reason, so a failed probe can never look like a successful empty catalog. Provenance enumerates every contributing config or registry source; registry entries also name the source section, such as `ai_models.yaml` → `agent_review_models` for Copilot policy. The mirror also records exact installed harness identity/version evidence, Ralph defaults, and consumer adapters.

Generation fails closed when the canonical `cursor_models` section is missing, empty, unrecognized, duplicated, or contains an invalid ID. Every non-command Ralph role default must also exist in the curated catalog for its Cursor/Pi harness; generation cannot publish a known mirror with a stale fallback.

Static generation has no network path:

```bash
python3 scripts/model_mirrors.py generate
python3 scripts/model_mirrors.py verify
```

The stable launcher adapter emits `consumer_view.v1` fields (`schema_version`, `consumer`, `harness`, `set`, `status`, `complete`, `models`, `reason`, `provenance`):

```bash
python3 scripts/model_mirrors.py adapt \
  --mirror home/dot_config/ai/readonly_model-mirrors.v1.json \
  --consumer launcher --harness cursor --set available
```

The deployed `,ai` launcher consumes the shared `consumer_view.v1` module with the `available` set. A known, complete catalog rejects an absent explicit model; incomplete or unknown catalogs preserve low-level explicit model control. The plan exposes bounded catalog status, count, and provenance without embedding the full model list, and planning performs no network access. Omitting `--set` in the repo-side adapter still selects the documented launcher default, `recommended`. Ralph preflight consumes `curated`, Ralph TUI consumes `recommended`, and `__comma_provider_models.fish` consumes provider `curated` catalogs. The generated Go consumer also mirrors Ralph's existing role fallback defaults, including the Claude/GPT reviewer-family split.

## Opt-in live drift

Live catalog access exists only behind the explicit `probe` subcommand:

```bash
python3 scripts/model_mirrors.py probe \
  --mirror home/dot_config/ai/readonly_model-mirrors.v1.json \
  --target harness:cursor --target provider:openrouter
```

Locally verified adapters cover Cursor (`cursor-agent --list-models`), Pi (`pi --offline --list-models`), OpenCode (`opencode models`), OpenRouter, LiteLLM, Cloudflare Workers AI, Cloudflare's OpenAI-compatible gateway, and llama.cpp. Claude, Codex, Gemini, Copilot, Azure Foundry, and the LiteLLM Anthropic route remain explicitly unsupported until a complete local adapter is verified.

Command probes are capped at 20 seconds and 4 MiB; HTTP probes are capped at 10 seconds and 8 MiB. Results never include stderr, response headers, credentials, or exception text. Every provider model ID in an HTTP payload must be a string accepted by `MODEL_ID_RE`; one malformed or non-string ID makes the whole payload `unknown`, never known drift. Missing credentials, authentication/command failures, timeouts, oversized/empty/unparseable output, and unsupported adapters also return `unknown`. A known result reports `stale_curated`, `new_available`, and `recommended_unavailable`, but never mutates the static mirror or auto-promotes a live ID.

Fixture probes use a JSON `target_cases` map such as [`scripts/tests/fixtures/model_probe_cases.json`](../../../scripts/tests/fixtures/model_probe_cases.json); providing a fixture without a matching target fails closed instead of falling through to a live call. `,ralph doctor --live-models` uses the same mirror/probe seam for its non-mutating Cursor diagnostic.

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
