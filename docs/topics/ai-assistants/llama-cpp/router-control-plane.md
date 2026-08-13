---
sidebar_position: 2
title: Router control plane
---

# Router control plane

The router control plane is the local runtime layer for llama.cpp models. It maps short model ids to GGUF files, starts `llama-server` in router mode, and exposes load/unload/status commands through `,llama-cpp`.

## Mental model

`models.ini` is the preset: it names the models and their per-model defaults. `,llama-cpp` is the operator interface: it manages the shared server lifecycle and calls the model API.

The shipped preset defines these model ids. They inherit shared `[*]` defaults unless a section overrides `ctx-size` / `n-predict`. The router loads one at a time on demand.

## Using it

### Router preset

llama.cpp model routing and per-model defaults live in an INI preset:

- Source: [`home/dot_config/llama.cpp/models.ini.tmpl`](../../../../home/dot_config/llama.cpp/models.ini.tmpl)
- Target: `~/.config/llama.cpp/models.ini`

The shipped preset defines these short model ids:

| ID             | GGUF path                                                                   | Use                                      |
| -------------- | --------------------------------------------------------------------------- | ---------------------------------------- |
| `nemotron-3.5` | `~/.llama.cpp/models/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_XL.gguf` | Unsloth Nemotron agentic model           |
| `qwen3.5-9b`   | `~/.llama.cpp/models/Qwen3.5-9B-UD-Q4_K_XL.gguf`                            | Unsloth Qwen3.5 9B + dest-renamed mmproj |

They inherit shared `[*]` defaults:

- `ctx-size=262144`
- Metal offload
- flash attention
- Jinja chat templates
- q8 KV cache
- `reasoning=auto`
- `nemotron-3.5` sets in-model NextN MTP (`spec-type=draft-mtp`, `spec-draft-n-max=2`) plus Unsloth thinking sampling (`temp=0.6`, `top-p=0.95`, `min-p=0.01`)
- `qwen3.5-9b` forces `reasoning=on` (Small-series thinking is off by default) plus Unsloth coding sampling (`temp=0.6`, `top-p=0.95`, `top-k=20`, `min-p=0`)

Switch with `,llama-cpp load <id>` / `,llama-cpp unload <id>`.

The served default `ctx-size` is `262144`, matching Nemotron and Qwen3.5-9B. Claude Code's local settings use `autoCompactWindow=200000` to compact before the default 262144-token server context fills.

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
