---
sidebar_position: 2
title: Router control plane
---

# Router control plane

The router control plane is the local runtime layer for llama.cpp models. It maps short model ids to GGUF files, starts `llama-server` in router mode, and exposes load/unload/status commands through `,llama-cpp`.

## Mental model

`models.ini` is the preset: it names the models and their per-model defaults. `,llama-cpp` is the operator interface: it manages the shared server lifecycle and calls the model API.

The shipped preset defines three model ids: `local`, `local-max`, and `nemotron-3.5`. They inherit the same shared defaults, and the router loads one at a time on demand.

## Using it

### Router preset

llama.cpp model routing and per-model defaults live in an INI preset:

- Source: [`home/dot_config/llama.cpp/models.ini.tmpl`](../../../../home/dot_config/llama.cpp/models.ini.tmpl)
- Target: `~/.config/llama.cpp/models.ini`

The shipped preset defines three short model ids:

| ID             | GGUF path                                                               | Use                     |
| -------------- | ----------------------------------------------------------------------- | ----------------------- |
| `local`        | `~/.llama.cpp/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`                   | primary model           |
| `local-max`    | `~/.llama.cpp/models/Qwen3.6-35B-A3B-abliterated.Q4_K_M.gguf`           | refusal-removed sibling |
| `nemotron-3.5` | `~/.llama.cpp/models/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-Q4_K_M.gguf` | Nemotron agentic model  |

Both inherit shared `[*]` defaults:

- `ctx-size=262144`
- Metal offload
- flash attention
- Jinja chat templates
- q8 KV cache
- `reasoning=auto`

Switch with `,llama-cpp load <id>` / `,llama-cpp unload <id>`.

Local A/B testing showed no-reasoning mode improves latency and structured-output cleanliness, but makes Qwen3.6 less capable for agent work. Keep reasoning enabled by default and disable it only for narrow structured-output probes.

The served `ctx-size` is `262144`, matching Qwen3.6's native context and intentionally capping Nemotron 3.5 below its 1M model limit. Claude Code's local settings use `autoCompactWindow=200000` to compact before the server context fills.

```bash
,llama-cpp serve
curl -s http://localhost:8080/models | python3 -m json.tool
```

### Shared lifecycle

The four `*-llama-cpp` launchers use `,llama-cpp run -- <command>`. Each process holds a lease for the configured host and port:

1. A reachable router is joined. A router started manually with `,llama-cpp serve` is never stopped by the lease manager.
2. An absent loopback router is started from the configured preset and recorded with its PID and process-start identity.
3. The last consumer schedules that recorded process to stop after `LLAMA_CPP_GRACE_SECONDS` (default `600`). A new consumer during grace cancels the pending shutdown and reuses the loaded router; `0` restores immediate shutdown.

Automatic startup is limited to loopback hosts. A missing non-loopback router fails closed because the launcher cannot safely start or own a remote process. Stale lease files left by an uncatchable process exit are pruned on the next lifecycle operation.

Use `,llama-cpp stop` to end a lifecycle-owned router during its grace period. It never stops a manually started router. If a harness still holds a lease, the command refuses to interrupt it; `,llama-cpp stop --force` is the explicit override and will break those active sessions.

### Model-level control plane (`,llama-cpp`)

This repo ships a thin wrapper around `llama-server` router mode and its model API:

```bash
,llama-cpp serve                      # start llama-server router mode
,llama-cpp run -- <command> [args...] # acquire a shared router lease
,llama-cpp stop [--force]             # stop the lifecycle-owned router now
,llama-cpp status                     # loaded/unloaded state
,llama-cpp load <model-id> [<id> ...] # POST /models/load
,llama-cpp unload <model-id> [<id> ...]
,llama-cpp unload --all
```

## Reference

| Variable                  | Default                              | Purpose                                       |
| ------------------------- | ------------------------------------ | --------------------------------------------- |
| `LLAMA_CPP_HOST`          | `127.0.0.1`                          | llama.cpp host                                |
| `LLAMA_CPP_PORT`          | `8080`                               | llama.cpp port                                |
| `LLAMA_CPP_API_KEY`       | no auth header unless set            | optional server and request key               |
| `LLAMA_CPP_MODELS_PRESET` | `~/.config/llama.cpp/models.ini`     | alternate model preset                        |
| `LLAMA_CPP_LIFECYCLE_DIR` | `~/.local/state/llama-cpp/lifecycle` | lease, owner, router-log, and shutdown state  |
| `LLAMA_CPP_GRACE_SECONDS` | `600`                                | delay after the last lease; `0` stops at once |

`,llama-cpp` respects `LLAMA_CPP_HOST` / `LLAMA_CPP_PORT` / `LLAMA_CPP_API_KEY` / `LLAMA_CPP_MODELS_PRESET` (defaults: `127.0.0.1:8080`, no auth header unless `LLAMA_CPP_API_KEY` is set, preset at `~/.config/llama.cpp/models.ini`).

## Internals

The `,llama-cpp` command is a thin launcher. Its command library implements `serve`/`run`/`stop`/`status`/`load`/`unload`; `lifecycle.py` owns locking, leases, process identity, and cleanup. Its fish completion provides context-aware subcommand + model-id completions.

## Sources and verification

- [`home/exact_bin/executable_,llama-cpp`](../../../../home/exact_bin/executable_,llama-cpp) → `~/bin/,llama-cpp` (thin launcher)
- [`home/exact_lib/exact_,llama-cpp/main.sh`](../../../../home/exact_lib/exact_,llama-cpp/main.sh) → `~/lib/,llama-cpp/main.sh` (subcommand implementation: `serve`/`run`/`stop`/`status`/`load`/`unload`)
- [`home/exact_lib/exact_,llama-cpp/lifecycle.py`](../../../../home/exact_lib/exact_,llama-cpp/lifecycle.py) → `~/lib/,llama-cpp/lifecycle.py` (shared router leases, shutdown grace, and owned-process cleanup)
- [`home/dot_config/fish/completions/readonly_,llama-cpp.fish`](../../../../home/dot_config/fish/completions/readonly_,llama-cpp.fish) — context-aware subcommand + model-id completions
