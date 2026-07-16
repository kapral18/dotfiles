---
sidebar_position: 2
title: Router control plane
---

# Router control plane

The router control plane is the local runtime layer for llama.cpp models. It maps short model ids to GGUF files, starts `llama-server` in router mode, and exposes load/unload/status commands through `,llama-cpp`.

## Mental model

`models.ini` is the preset: it names the models and their per-model defaults. `,llama-cpp` is the operator interface: it starts the server and calls the model API.

The shipped preset defines two model ids, `local` and `local-max`; both inherit the same shared defaults and the router loads one at a time on demand.

## Using it

### Router preset

llama.cpp model routing and per-model defaults live in an INI preset:

- Source: [`home/dot_config/llama.cpp/models.ini.tmpl`](../../../../home/dot_config/llama.cpp/models.ini.tmpl)
- Target: `~/.config/llama.cpp/models.ini`

The shipped preset defines two short model ids:

| ID          | GGUF path                                                     | Use                     |
| ----------- | ------------------------------------------------------------- | ----------------------- |
| `local`     | `~/.llama.cpp/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`         | primary model           |
| `local-max` | `~/.llama.cpp/models/Qwen3.6-35B-A3B-abliterated.Q4_K_M.gguf` | refusal-removed sibling |

Both inherit shared `[*]` defaults:

- `ctx-size=262144`
- Metal offload
- flash attention
- Jinja chat templates
- q8 KV cache
- `reasoning=auto`

Switch with `,llama-cpp load <id>` / `,llama-cpp unload <id>`.

Local A/B testing showed no-reasoning mode improves latency and structured-output cleanliness, but makes Qwen3.6 less capable for agent work. Keep reasoning enabled by default and disable it only for narrow structured-output probes.

The default `ctx-size` is `262144`, matching the Qwen3.6 GGUF's native `qwen35moe.context_length`. Claude Code's local settings use `autoCompactWindow=200000` to compact before the server context fills.

```bash
,llama-cpp serve
curl -s http://localhost:8080/models | python3 -m json.tool
```

### Model-level control plane (`,llama-cpp`)

This repo ships a thin wrapper around `llama-server` router mode and its model API:

```bash
,llama-cpp serve                      # start llama-server router mode
,llama-cpp status                     # loaded/unloaded state
,llama-cpp load <model-id> [<id> ...] # POST /models/load
,llama-cpp unload <model-id> [<id> ...]
,llama-cpp unload --all
```

## Reference

| Variable                  | Default                          | Purpose                    |
| ------------------------- | -------------------------------- | -------------------------- |
| `LLAMA_CPP_HOST`          | `127.0.0.1`                      | llama.cpp host             |
| `LLAMA_CPP_PORT`          | `8080`                           | llama.cpp port             |
| `LLAMA_CPP_API_KEY`       | no auth header unless set        | optional auth header value |
| `LLAMA_CPP_MODELS_PRESET` | `~/.config/llama.cpp/models.ini` | alternate model preset     |

`,llama-cpp` respects `LLAMA_CPP_HOST` / `LLAMA_CPP_PORT` / `LLAMA_CPP_API_KEY` / `LLAMA_CPP_MODELS_PRESET` (defaults: `127.0.0.1:8080`, no auth header unless `LLAMA_CPP_API_KEY` is set, preset at `~/.config/llama.cpp/models.ini`).

## Internals

The `,llama-cpp` command is a thin launcher. Its command library implements `serve`/`status`/`load`/`unload`, and its fish completion provides context-aware subcommand + model-id completions.

## Sources and verification

- [`home/exact_bin/executable_,llama-cpp`](../../../../home/exact_bin/executable_,llama-cpp) → `~/bin/,llama-cpp` (thin launcher)
- [`home/exact_lib/exact_,llama-cpp/main.sh`](../../../../home/exact_lib/exact_,llama-cpp/main.sh) → `~/lib/,llama-cpp/main.sh` (subcommand implementation: `serve`/`status`/`load`/`unload`)
- [`home/dot_config/fish/completions/readonly_,llama-cpp.fish`](../../../../home/dot_config/fish/completions/readonly_,llama-cpp.fish) — context-aware subcommand + model-id completions
