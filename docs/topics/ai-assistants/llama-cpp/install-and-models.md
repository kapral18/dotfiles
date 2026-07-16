---
sidebar_position: 1
title: Install and models
---

# Install and models

This page covers the local llama.cpp installation and the curated GGUF files the router can load. The tool install is Homebrew-managed; the model download is opt-in because the weights are multi-GB artifacts.

## Mental model

Homebrew installs `llama.cpp` and the official Hugging Face CLI (`hf`). A chezmoi-templated manifest names the GGUF checkpoints that should exist under `~/.llama.cpp/models/`.

`chezmoi apply` only downloads those checkpoints when `downloadLlamaCppModels` is enabled in `~/.config/chezmoi/chezmoi.toml`; the default is `false`.

## Using it

### Install

`llama.cpp` and the official Hugging Face CLI (`hf`) are installed via Homebrew ([`home/readonly_dot_Brewfile.tmpl`](../../../../home/readonly_dot_Brewfile.tmpl), AI & LARGE LANGUAGE MODELS section):

```ruby
brew "llama.cpp"
brew "hf"
```

### Model manifest

The curated GGUF model list is a chezmoi-templated manifest: [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../../../home/readonly_dot_default-llama-cpp-models.tmpl). It keeps two checkpoints:

- **Primary** (router id `local`) — `unsloth/Qwen3.6-35B-A3B-GGUF` with `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (~22.4 GB). The Unsloth dynamic (UD) quant is higher fidelity than stock `Q4_K_M` at the same size class, and the full 262144-token context still co-fits in 36 GB unified memory alongside the q8_0 KV cache.
- **Abliterated sibling** (router id `local-max`) — `mradermacher/Qwen3.6-35B-A3B-abliterated-GGUF` with `Qwen3.6-35B-A3B-abliterated.Q4_K_M.gguf` (~21.2 GB). A refusal-removed abliteration of the same base model, for prompts the stock model declines. Both GGUFs stay on disk; the router loads one at a time on demand.

### Sync hook (opt-in)

Downloads are gated by `downloadLlamaCppModels` in `~/.config/chezmoi/chezmoi.toml`. Default is `false`, so `chezmoi apply` never auto-downloads multi-GB weights unless explicitly enabled.

To change the setting, clear that key and re-run `chezmoi init`.

```bash
chezmoi init  # (once) prompts for downloadLlamaCppModels
chezmoi apply # syncs models when gate is true
,llama-cpp serve
```

## Reference

Format (pipe-delimited): `<hf-repo-id>|<hf-file>`

| Field        | Meaning                                             |
| ------------ | --------------------------------------------------- |
| `hf-repo-id` | Hugging Face repo id containing GGUF weights        |
| `hf-file`    | GGUF filename to place under `~/.llama.cpp/models/` |

## Internals

The sync hook is a thin shell orchestrator that delegates parse + skip + download logic to a Python helper.

The helper treats a GGUF file as "complete" if it exists and has non-zero size, so re-runs are idempotent. Override the model root with `LLAMA_CPP_MODELS_ROOT` (defaults to `~/.llama.cpp/models`).

## Sources and verification

- [`home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl)
- [`scripts/sync_llama_cpp_models.py`](../../../../scripts/sync_llama_cpp_models.py)
