---
sidebar_position: 9
---

# Model Registry & Routing

Canonical model policy stays in the existing YAML and per-harness configs. Generated mirrors project that policy into one machine-readable view without becoming a competing source of truth.

This is the model-side counterpart to the [MCP registry](mcp.md). Use it when adding a model, changing reasoning/cost metadata, checking live catalog drift, or understanding how a model reaches Pi, OpenCode, and provider launchers.

## Mental model

| Piece                                                                                                             | Role                                                                        |
| ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| [`home/.chezmoidata/ai_models/`](../../../home/.chezmoidata/ai_models)                                            | Canonical model registry and policy sections, split across three files      |
| [`scripts/ai_models.py`](../../../scripts/ai_models.py)                                                           | Dependency-free parser for the registry sections                            |
| [`home/dot_config/ai/readonly_model-mirrors.v1.json`](../../../home/dot_config/ai/readonly_model-mirrors.v1.json) | Committed generated mirror deployed to `~/.config/ai/model-mirrors.v1.json` |
| [`scripts/model_mirrors.py`](../../../scripts/model_mirrors.py)                                                   | Generates/verifies the static mirror and runs explicit live drift probes    |

## Registry: `.chezmoidata/ai_models/`

Source of truth: [`home/.chezmoidata/ai_models/`](../../../home/.chezmoidata/ai_models). The sections are split across three files for navigation only — chezmoi merges every file under `.chezmoidata/` (subdirectories included) into one flat data namespace, so templates still read `.cursor_models` and `.model_bands` directly. [`scripts/ai_models.py`](../../../scripts/ai_models.py) holds the section → file map (`SECTION_FILES`) and takes the registry directory, never a single file.

| Section               | File                    | Canonical policy                                                                                                                  |
| --------------------- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `cursor_models`       | `harness-catalogs.yaml` | Curated Cursor aliases; `recommended: true` is the narrower preferred set                                                         |
| `pi_extra_models`     | `harness-catalogs.yaml` | Pi's curated picker; every entry is provider-routed through Pi's built-in OpenRouter provider                                     |
| `copilot_models`      | `harness-catalogs.yaml` | Probed Copilot CLI catalog; the mirror's copilot `available` set                                                                  |
| `provider_models`     | `provider-routes.yaml`  | Static provider-route choices for shell completion; Vertex entries also own adapter wire/capability metadata                      |
| `agent_review_models` | `tiering.yaml`          | Per-harness review `lanes`/`verifier` pairs; the verifier-family pairing is reviewed here rather than inferred or auto-promoted   |
| `agent_categories`    | `tiering.yaml`          | Portable category → `{band, family}`; the same table on every harness                                                             |
| `agent_bindings`      | `tiering.yaml`          | Every delegable agent name → its category, built-ins included                                                                     |
| `model_bands`         | `tiering.yaml`          | Per-harness `cheap`/`standard`/`max` picks (+ `counter` on `max`); see [Model tiering](model-tiering.md) for policy and rationale |

Adding a section means adding it to `SECTION_FILES` as well: the parser resolves a section by name, so an unmapped section raises rather than being searched for across files.

Recommended Cursor entries use `recommendation_rank` to preserve the deliberate TUI picker order independently of the broader curated registry order.

Vertex entries keep the adapter's routing contract in the same canonical section: `backend` selects Gemini Chat Completions or Claude publisher raw prediction, `wire_model` is the exact upstream ID, `efforts` and `supports_no_thinking` define accepted reasoning controls, and one `adapter_default` selects the no-argument model. `home/dot_config/vertex-adapter/readonly_models.json.tmpl` projects the registry into `~/.config/vertex-adapter/models.json`; the deployed adapter filters the `vertex` provider and fails if the default or model IDs are ambiguous.

## Using it

Static generation has no network path:

```bash
python3 scripts/model_mirrors.py generate
python3 scripts/model_mirrors.py verify
```

The stable launcher adapter emits `consumer_view.v1` fields:

```text
schema_version, consumer, harness, set, status, complete, models, reason, provenance
```

Example adapter call:

```bash
python3 scripts/model_mirrors.py adapt \
  --mirror home/dot_config/ai/readonly_model-mirrors.v1.json \
  --consumer launcher --harness cursor --set available
```

Live catalog access exists only behind the explicit `probe` subcommand:

```bash
python3 scripts/model_mirrors.py probe \
  --mirror home/dot_config/ai/readonly_model-mirrors.v1.json \
  --target harness:cursor --target provider:openrouter
```

## Generators

| Generator                                                                                                                       | Output                                                                      |
| ------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| [`scripts/model_mirrors.py`](../../../scripts/model_mirrors.py)                                                                 | Generates/verifies the v1 static mirror and runs explicit live drift probes |
| [`home/dot_config/vertex-adapter/readonly_models.json.tmpl`](../../../home/dot_config/vertex-adapter/readonly_models.json.tmpl) | Renders provider metadata consumed by the three per-session Vertex wrappers |

Pi and OpenCode no longer generate model blocks: both harnesses resolve `openrouter/` selectors through their own built-in provider, so `run_onchange_after_07-merge-pi-config.sh.tmpl` installs the profile's static `models.json` and `run_onchange_after_07-merge-opencode-config.sh.tmpl` only injects MCP servers.

The mirror is a committed generated artifact verified by tests and `make check`. Diagnostic probes are operator initiated. See [Tool configs](tool-configs/index.md).

## Generated mirror v1

[`home/dot_config/ai/readonly_model-mirrors.v1.json`](../../../home/dot_config/ai/readonly_model-mirrors.v1.json) deploys to `~/.config/ai/model-mirrors.v1.json`.

It is generated from the registry, harness configs, and the versioned installed-harness evidence in [`scripts/model_capabilities.v1.json`](../../../scripts/model_capabilities.v1.json).

`observed_at` is the verification date for that evidence snapshot, not a claim about the currently installed binaries. Refresh the identities and their catalog/capability claims together before advancing it; a newer `--version` alone is not equivalent evidence.

Every harness and provider route has three catalogs:

| Catalog       | Meaning                                                                                               |
| ------------- | ----------------------------------------------------------------------------------------------------- |
| `available`   | What fixed installed-source evidence or configured capability data establishes; may be incomplete     |
| `curated`     | Operator-owned IDs allowed by current policy                                                          |
| `recommended` | Deliberate subset shown as preferred choices; availability alone never promotes a model into this set |

Each catalog carries `status`, `models`, `complete`, `reason`, and `provenance`. Status is `known`, `unknown`, or `error`.

`unknown`/`error` catalogs must have no models, `complete: null`, and a reason, so a failed probe can never look like a successful empty catalog.

Provenance enumerates every contributing config or registry source. Registry entries also name the source section, such as `ai_models/tiering.yaml` → `agent_review_models` for Copilot policy.

The mirror also records exact installed harness identity/version evidence and consumer adapters.

Generation fails closed when the canonical `cursor_models` section is missing, empty, unrecognized, duplicated, or contains an invalid ID. Curated catalogs must contain only recognized, non-duplicated IDs; generation cannot publish a known mirror with a stale fallback.

### Launcher consumption

The deployed `,ai` launcher consumes the shared `consumer_view.v1` module with the `available` set.

A known, complete catalog rejects an absent explicit model. Incomplete or unknown catalogs preserve low-level explicit model control.

The plan exposes bounded catalog status, count, and provenance without embedding the full model list, and planning performs no network access.

Omitting `--set` in the repo-side adapter still selects the documented launcher default, `recommended`. `__comma_provider_models.fish` consumes provider `curated` catalogs.

Command consumers keep policy in their own config and use the mirror only for bounded availability/provenance checks.

## Opt-in live drift

Locally verified adapters cover Cursor (`cursor-agent --list-models`), Pi (`pi --offline --list-models`), OpenCode (`opencode models`), OpenRouter, Vertex, and llama.cpp.

Claude, Codex, Gemini, and Copilot remain explicitly unsupported until a complete local adapter is verified.

Probe limits and failure rules:

| Probe type     | Cap                  |
| -------------- | -------------------- |
| Command probes | 20 seconds and 4 MiB |
| HTTP probes    | 10 seconds and 8 MiB |

Results never include stderr, response headers, credentials, or exception text.

Every provider model ID in an HTTP payload must be a string accepted by `MODEL_ID_RE`. One malformed or non-string ID makes the whole payload `unknown`, never known drift.

Missing credentials, authentication/command failures, timeouts, oversized/empty/unparseable output, and unsupported adapters also return `unknown`.

A known result reports `stale_curated`, `new_available`, and `recommended_unavailable`, but never mutates the static mirror or auto-promotes a live ID.

Fixture probes use a JSON `target_cases` map such as [`scripts/tests/fixtures/model_probe_cases.json`](../../../scripts/tests/fixtures/model_probe_cases.json). Providing a fixture without a matching target fails closed instead of falling through to a live call.

The same mirror/probe seam is available for non-mutating live catalog diagnostics.

## OpenRouter routing

`OPENROUTER_API_KEY` comes from the `openrouter/api/token` pass entry, exported by [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../home/dot_config/fish/readonly_config.fish.tmpl). Both Pi and OpenCode resolve `openrouter/` selectors through their own built-in provider, so neither carries a generated provider block.

Upstream provider routing is model-specific (user calls 2026-08-07; uptime-aware default load balancing 2026-08-17): every `moonshotai/kimi-k3` route sends `provider: { only: ["fireworks", "together", "baseten"], max_price: { completion: 16 } }`, while every `deepseek/deepseek-v4-flash-0731` route sends `provider: { quantizations: ["fp8", "fp16", "bf16", "fp32"], preferred_min_throughput: 24 }`; `z-ai/glm-5.2` carries the same FP8-or-higher, 24 t/s floor policy as DeepSeek. None of these objects set `sort` or `order`: OpenRouter's default load balancer then skips providers with significant outages in the last 30 seconds and price-weights the rest. The DeepSeek/GLM allowlist excludes INT4/INT8/FP4/FP6 providers; `preferred_min_throughput` deprioritizes endpoints below 24 t/s rather than excluding them. See [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).

The policies have three carriers. Pi 0.84.0 sends each object through `modelOverrides.compat.openRouterRouting`, which its runtime copies as-is into the request's `provider` field. OMP 17.2.9's typed openrouter transport drops `modelOverrides…compat.extraBody.provider` from the wire (verified 2026-08-08: the merged catalog entry carries no extraBody and a live request with an impossible quantization succeeds), so OMP and OpenCode carry the policy in the model slug through workspace `*-lanes-*` presets. The eight `kimi-lanes*` presets preserve their effort-specific `reasoning.effort` values (including `none`, which disables reasoning) and carry the Kimi object; the eight `deepseek-lanes*` and eight `glm-lanes*` presets do the same for DeepSeek and GLM-5.2, including the FP8-or-higher quantization allowlist. The four `*-openrouter` wrappers compose effort only: `<model>@preset/effort-<level>` for every `--model`. `,cursor-openrouter` reaches OpenRouter through Cursor's agent-cli-local flavor (`--base-url` OpenAI-compatible), which the regular cursor-agent build rejects; its provider config is baseUrl+apiKey only, so effort rides the `effort-<level>` slug. Every session runs through the loopback shim, which both strips `strict:true` from `openai/*` tool schemas (cursor-agent-local's reasoning predicate matches those ids and the bundled Shell schema's optional `debounce_ms` fails OpenAI strict validation; see [other harnesses](tool-configs/other-harnesses.md)) and enforces a wire-level model allowlist: the launcher exports the pinned wire id as `CURSOR_AGENT_ALLOWED_MODEL` and the shim returns 403 for any `/chat/completions` whose model differs, so no subagent or profile can route a different model on the session. The wrappers default to `deepseek/deepseek-v4-flash-0731@preset/effort-max`. Inside an interactive session `/model` accepts a free-text id verbatim, so a typed `model@preset/effort-<level>` keeps the effort slug while a bare model does not.

- **OpenCode**: both profiles run `main`, every configured worker, and `small_model` on `openrouter/deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max` at `max` effort. Kimi stays available through `openrouter/moonshotai/kimi-k3@preset/kimi-lanes`; GLM-5.2 is selectable through `openrouter/z-ai/glm-5.2@preset/glm-lanes-max`.
- **Pi**: `defaultProvider` is `openrouter` in both profiles, and `pi_extra_models` exposes the strict OpenRouter route: `openrouter/deepseek/deepseek-v4-flash-0731` (recommended/default/lanes), `openrouter/moonshotai/kimi-k3` (selectable), `openrouter/z-ai/glm-5.2` (selectable), and `openrouter/openai/gpt-5.6-terra` (counter/verifier only). The three gated models carry their policy through `modelOverrides`.

## Local inference

The local-inference backend is llama.cpp via `,llama-cpp`; see [llama.cpp local inference](llama-cpp/index.md).

## Related

- [MCP servers](mcp.md) — the parallel registry for tool servers
- [Tool configs](tool-configs/index.md) — per-assistant settings and profile merging
- [llama.cpp local inference](llama-cpp/index.md) — local GGUF backend
