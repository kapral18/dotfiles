---
sidebar_position: 8
---

# llama.cpp Local Inference

[llama.cpp](https://github.com/ggml-org/llama.cpp) provides `llama-server`, a local C/C++ inference server with OpenAI-compatible chat/completions/responses endpoints and Anthropic-compatible `/v1/messages` endpoints. It is the primary local-agentic-coding backend.

Use when serving local GGUF models, wiring a local provider into Pi/Claude/Codex, or managing the model router. To add a model to the manifest, see the recipe [Add a llama.cpp model](../core/packages/llama-cpp-model.md).

## Install

`llama.cpp` and the official Hugging Face CLI (`hf`) are installed via Homebrew ([`home/readonly_dot_Brewfile.tmpl`](../../../home/readonly_dot_Brewfile.tmpl), AI & LARGE LANGUAGE MODELS section):

```ruby
brew "llama.cpp"
brew "hf"
```

## Model manifest

The curated GGUF model list is a chezmoi-templated manifest: [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../../home/readonly_dot_default-llama-cpp-models.tmpl). It keeps two checkpoints:

- **Primary** (router id `local`) — `unsloth/Qwen3.6-35B-A3B-GGUF` with `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (~22.4 GB). The Unsloth dynamic (UD) quant is higher fidelity than stock `Q4_K_M` at the same size class, and the full 262144-token context still co-fits in 36 GB unified memory alongside the q8_0 KV cache.
- **Abliterated sibling** (router id `local-max`) — `mradermacher/Qwen3.6-35B-A3B-abliterated-GGUF` with `Qwen3.6-35B-A3B-abliterated.Q4_K_M.gguf` (~21.2 GB). A refusal-removed abliteration of the same base model, for prompts the stock model declines. Both GGUFs stay on disk; the router loads one at a time on demand.

Format (pipe-delimited): `<hf-repo-id>|<hf-file>`

- `hf-repo-id` — Hugging Face repo id containing GGUF weights.
- `hf-file` — GGUF filename to place under `~/.llama.cpp/models/`.

## Sync hook (opt-in)

Downloads are gated by `downloadLlamaCppModels` in `~/.config/chezmoi/chezmoi.toml`. Default is `false`, so `chezmoi apply` never auto-downloads multi-GB weights unless explicitly enabled. To change the setting, clear that key and re-run `chezmoi init`.

The sync hook is a thin shell orchestrator that delegates parse + skip + download logic to a Python helper:

- [`home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl`](../../../home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl)
- [`scripts/sync_llama_cpp_models.py`](../../../scripts/sync_llama_cpp_models.py)

The helper treats a GGUF file as "complete" if it exists and has non-zero size, so re-runs are idempotent. Override the model root with `LLAMA_CPP_MODELS_ROOT` (defaults to `~/.llama.cpp/models`).

```bash
chezmoi init  # (once) prompts for downloadLlamaCppModels
chezmoi apply # syncs models when gate is true
,llama-cpp serve
```

## Router preset

llama.cpp model routing and per-model defaults live in an INI preset:

- Source: [`home/dot_config/llama.cpp/models.ini.tmpl`](../../../home/dot_config/llama.cpp/models.ini.tmpl)
- Target: `~/.config/llama.cpp/models.ini`

The shipped preset defines two short model ids: `local` (primary, pointing at `~/.llama.cpp/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`) and `local-max` (the refusal-removed abliterated sibling, pointing at `~/.llama.cpp/models/Qwen3.6-35B-A3B-abliterated.Q4_K_M.gguf`). Both inherit the shared `[*]` defaults for `ctx-size=262144`, Metal offload, flash attention, Jinja chat templates, q8 KV cache, and `reasoning=auto`. Switch between them with `,llama-cpp load <id>` / `,llama-cpp unload <id>`. Local A/B testing showed no-reasoning mode improves latency and structured-output cleanliness, but it makes Qwen3.6 noticeably less capable for agent work; keep reasoning enabled by default and disable it only for narrow structured-output probes.

The default `ctx-size` is `262144`, matching the Qwen3.6 GGUF's native `qwen35moe.context_length`. Claude Code's local settings use `autoCompactWindow=200000` to compact before the server context fills.

```bash
,llama-cpp serve
curl -s http://localhost:8080/models | python3 -m json.tool
```

## Model-level control plane (`,llama-cpp`)

This repo ships a thin wrapper around `llama-server` router mode and its model API:

- [`home/exact_bin/executable_,llama-cpp`](../../../home/exact_bin/executable_,llama-cpp) → `~/bin/,llama-cpp`
- [`home/dot_config/fish/completions/readonly_,llama-cpp.fish`](../../../home/dot_config/fish/completions/readonly_,llama-cpp.fish) — context-aware subcommand + model-id completions

```bash
,llama-cpp serve                      # start llama-server router mode
,llama-cpp status                     # loaded/unloaded state
,llama-cpp load <model-id> [<id> ...] # POST /models/load
,llama-cpp unload <model-id> [<id> ...]
,llama-cpp unload --all
```

Respects `LLAMA_CPP_HOST` / `LLAMA_CPP_PORT` / `LLAMA_CPP_API_KEY` / `LLAMA_CPP_MODELS_PRESET` (defaults: `127.0.0.1:8080`, no auth header unless `LLAMA_CPP_API_KEY` is set, preset at `~/.config/llama.cpp/models.ini`).

## Pi provider

Pi settings and models are installed readonly, so the llama.cpp provider is declared once in shared chezmoi source and rendered into `~/.pi/agent/models.json` for both profiles:

- Shared source: [`home/dot_pi/agent/readonly_models.json`](../../../home/dot_pi/agent/readonly_models.json)
- Work source: [`scripts/generate_pi_models.py`](../../../scripts/generate_pi_models.py) starts from that shared source, then adds work-only LiteLLM and Azure providers

```bash
,llama-cpp serve
pi --model llama-cpp/local       # primary
pi --model llama-cpp/local-max   # abliterated sibling
```

The provider declares both `local` and `local-max`, points Pi at `http://127.0.0.1:8080/v1` with `api: "openai-completions"` and Qwen chat-template thinking compatibility. The `apiKey` uses the `!command` form (`!printf ...`) and the work LiteLLM/Azure keys use `$ENV_VAR` syntax, so Pi's startup config migration finds nothing to rewrite and never attempts to write the read-only `~/.pi/agent/models.json`. If you start `llama-server` with `--api-key`, export `LLAMA_CPP_API_KEY` before launching Pi.

## Codex launcher metadata

Codex only has first-class model metadata for slugs present in its model catalog; unknown local slugs use fallback metadata and emit a warning. This repo ships a transparent `codex` wrapper plus a small local catalog for the llama.cpp models:

- [`home/exact_bin/executable_codex`](../../../home/exact_bin/executable_codex) → `~/bin/codex`
- [`home/dot_codex/readonly_llama-cpp-model-catalog.json`](../../../home/dot_codex/readonly_llama-cpp-model-catalog.json) → `~/.codex/llama-cpp-model-catalog.json` (defines both `local` and `local-max`)

The wrapper injects `-c model_catalog_json="$HOME/.codex/llama-cpp-model-catalog.json"` when the selected model is one of the local llama.cpp ids (`local` or `local-max`), in either `--model <id>` or `--model=<id>` form; normal Codex invocations fall through to `/opt/homebrew/bin/codex` unchanged.

## Codex launcher (`,codex-llama-cpp`)

The `codex` shim above only supplies catalog metadata; Codex still needs the provider routing flags to reach llama-server. `,codex-llama-cpp` bakes those in so you don't type them every time:

- [`home/exact_bin/executable_,codex-llama-cpp`](../../../home/exact_bin/executable_,codex-llama-cpp) → `~/bin/,codex-llama-cpp`

It injects `-c model_providers.llama-cpp.base_url="http://${LLAMA_CPP_HOST}:${LLAMA_CPP_PORT}/v1" -c model_providers.llama-cpp.name="llama.cpp" -c model_provider="llama-cpp"` (the `~/bin/codex` shim still injects the catalog json). Pass `--model`/`-m local-max` to pick the model; the wrapper only injects its default `--model $CODEX_LLAMA_CPP_MODEL` (default `local`) when you did not pass one, so there is no duplicate flag.

```bash
,codex-llama-cpp                          # default model local
,codex-llama-cpp --model local-max        # abliterated sibling
,codex-llama-cpp -m local-max exec "..."  # one-shot
```

## OpenCode launcher (`,opencode-llama-cpp`)

OpenCode reads providers from `~/.config/opencode/opencode.jsonc` (no per-invocation override), so the `llama-cpp` provider (`baseURL http://127.0.0.1:8080/v1`, models `local` + `local-max`) is declared in both profile sources and flows through the merge hook unchanged. The provider id avoids a dot (`llama-cpp`, not `llama.cpp`) because OpenCode's SDK derives an incorrect lookup key from dotted ids.

- [`home/dot_config/opencode/readonly_opencode.personal.jsonc`](../../../home/dot_config/opencode/readonly_opencode.personal.jsonc) / [`readonly_opencode.work.jsonc`](../../../home/dot_config/opencode/readonly_opencode.work.jsonc) — declare the `llama-cpp` provider
- [`home/exact_bin/executable_,opencode-llama-cpp`](../../../home/exact_bin/executable_,opencode-llama-cpp) → `~/bin/,opencode-llama-cpp`

Pass `--model`/`-m` with a bare id (`local`/`local-max`) — the wrapper qualifies it to `llama-cpp/<id>` — or the full `llama-cpp/<id>`. With no `--model`, it defaults to `llama-cpp/$OPENCODE_LLAMA_CPP_MODEL` (`local`). Any subcommand/args pass through.

```bash
,opencode-llama-cpp                            # interactive TUI, default model local
,opencode-llama-cpp --model local-max          # abliterated sibling (bare id auto-qualified)
,opencode-llama-cpp --model local-max run "…"  # one-shot
```

## Claude Code launcher (`,claude-llama-cpp`)

Claude Code compacts conversation history at `autoCompactWindow` tokens (schema min 100000, max 1000000). Cloud `opus[1m]` sessions benefit from leaving this at the default (~1M). Local llama.cpp sessions need it below the server context so Claude Code compacts before llama.cpp rejects the prompt. Those two needs conflict on a single global value.

Solution: a dedicated llama.cpp-scoped settings file loaded via `claude --settings <file>` (layers additively on top of `~/.claude/settings.json`), wired through a thin wrapper.

- [`home/dot_claude/settings.llama-cpp.json`](../../../home/dot_claude/settings.llama-cpp.json) → `~/.claude/settings.llama-cpp.json` (contains only `autoCompactWindow: 200000`)
- [`home/exact_bin/executable_,claude-llama-cpp`](../../../home/exact_bin/executable_,claude-llama-cpp) → `~/bin/,claude-llama-cpp`

The wrapper exports `ANTHROPIC_BASE_URL=http://${LLAMA_CPP_HOST:-127.0.0.1}:${LLAMA_CPP_PORT:-8080}`, sets `ANTHROPIC_API_KEY=$LLAMA_CPP_API_KEY` (defaults to `sk-no-key-required` because llama.cpp accepts unauthenticated local requests unless started with `--api-key`), and invokes `claude --settings ~/.claude/settings.llama-cpp.json "$@"`. Pass `--model`/`-m local-max` to pick the model; the wrapper only injects its default `--model $CLAUDE_LLAMA_CPP_MODEL` when you did not pass one, so there is no duplicate flag.

| Variable                    | Default                                 | Purpose                                                             |
| --------------------------- | --------------------------------------- | ------------------------------------------------------------------- |
| `LLAMA_CPP_HOST`            | `127.0.0.1`                             | Same as `,llama-cpp`                                                |
| `LLAMA_CPP_PORT`            | `8080`                                  | Same as `,llama-cpp`                                                |
| `LLAMA_CPP_API_KEY`         | `sk-no-key-required`                    | Sent as `ANTHROPIC_API_KEY` (Claude Code uses this for bearer auth) |
| `CLAUDE_LLAMA_CPP_MODEL`    | `local`                                 | Default model; overridden by a caller `--model`/`-m`, empty to skip |
| `CLAUDE_LLAMA_CPP_SETTINGS` | `$HOME/.claude/settings.llama-cpp.json` | Point at an alternate llama.cpp settings file                       |

`autoCompactWindow=200000` leaves ~62k headroom under the 262144-token server context for the next turn's prompt, tool outputs, and model reply.

```bash
,claude-llama-cpp                           # interactive session, default model local
,claude-llama-cpp -p "summarize README.md"  # one-shot prompt
,claude-llama-cpp --model local-max         # use the abliterated sibling
```

Cloud Claude sessions are unaffected — plain `claude ...` still reads only `~/.claude/settings.json`, where `autoCompactWindow` stays unset so the default for `opus[1m]` applies.

## Related

- [Add a llama.cpp model](../core/packages/llama-cpp-model.md) — manifest recipe
- [Model registry & routing](model-registry.md) — cloud model definitions
- [Ralph orchestrator](ralph.md) — opt-in local models for roles
