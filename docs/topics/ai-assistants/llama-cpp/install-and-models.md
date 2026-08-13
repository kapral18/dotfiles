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

The curated GGUF model list is a chezmoi-templated manifest: [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../../../home/readonly_dot_default-llama-cpp-models.tmpl). Companion files (mmproj, DFlash drafter) are extra manifest lines; they are not router ids.

| Router id      | Checkpoint                                                                                                              | Notes                                                                                              |
| -------------- | ----------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `nemotron-3.5` | `unsloth/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF` `NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_XL.gguf` (~25.5 GB) | Unsloth Dynamic quant; in-model NextN MTP + thinking sampling in `models.ini`                      |
| `qwen3.5-9b`   | `unsloth/Qwen3.5-9B-GGUF` `Qwen3.5-9B-UD-Q4_K_XL.gguf` (~6.0 GB) plus dest `Qwen3.5-9B-mmproj-F16.gguf`                 | Unsloth Dynamic quant; mmproj dest-renamed so the Hugging Face `mmproj-F16.gguf` name stays unique |

The router loads one preset at a time on demand. Weights stay on disk.

### Sync hook (opt-in)

Downloads are gated by `downloadLlamaCppModels` in `~/.config/chezmoi/chezmoi.toml`. Default is `false`, so `chezmoi apply` never auto-downloads multi-GB weights unless explicitly enabled.

To change the setting, clear that key and re-run `chezmoi init`.

```bash
chezmoi init  # (once) prompts for downloadLlamaCppModels
chezmoi apply # syncs models when gate is true
,llama-cpp serve
```

## Reference

Format (pipe-delimited): `<hf-repo-id>|<hf-file>` or `<hf-repo-id>|<hf-file>|<dest-basename>`

| Field           | Meaning                                                                                |
| --------------- | -------------------------------------------------------------------------------------- |
| `hf-repo-id`    | Hugging Face repo id containing GGUF weights                                           |
| `hf-file`       | GGUF filename in that repo                                                             |
| `dest-basename` | Optional on-disk name under `~/.llama.cpp/models/` when the Hugging Face name collides |

## Internals

The sync hook is a thin shell orchestrator that delegates parse + skip + download logic to a Python helper.

The helper treats a GGUF file as "complete" if the dest path exists and has non-zero size, so re-runs are idempotent. A same dest from a different Hugging Face repo is treated as present; swapping repos requires replacing the on-disk file. When dest differs from `hf-file`, the download is staged in a temp directory and renamed so the Hugging Face name cannot overwrite a sibling. Override the model root with `LLAMA_CPP_MODELS_ROOT` (defaults to `~/.llama.cpp/models`).

## Sources and verification

- [`home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl)
- [`scripts/sync_llama_cpp_models.py`](../../../../scripts/sync_llama_cpp_models.py)
