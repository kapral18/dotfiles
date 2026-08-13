---
sidebar_position: 18
---

# Add A llama.cpp Model

llama.cpp models are pulled into `~/.llama.cpp/models/` from a curated GGUF manifest. Downloads are opt-in and idempotent.

## Preconditions

- `llama-server` and `hf` are installed (Brewfile additions in the AI section).
- You ran `chezmoi init` at least once and chose a value for `downloadLlamaCppModels`. Clear that key from `~/.config/chezmoi/chezmoi.toml` and re-run `chezmoi init` to change it.
- You identified a GGUF Hugging Face repo and the exact `.gguf` filename to download.

## Where The List Lives

- [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../../../home/readonly_dot_default-llama-cpp-models.tmpl)

## Schema

Pipe-delimited, one model per line:

```text
<hf-repo-id>|<hf-file>
<hf-repo-id>|<hf-file>|<dest-basename>
```

- `hf-repo-id` — Hugging Face repo id containing GGUF weights.
- `hf-file` — GGUF filename in that repo.
- `dest-basename` — optional on-disk name under `~/.llama.cpp/models/`. Use it when two Hugging Face files share a name (for example `mmproj-F16.gguf`). The helper stages that download in a temp directory and renames it so the Hugging Face name cannot overwrite a sibling.

Lines starting with `#` and blank lines are ignored. Chezmoi template conditionals work natively if a future model should render only for a specific profile; the orchestrator pipes the manifest through `chezmoi execute-template`.

## Steps

1. Add or edit the entry in [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../../../home/readonly_dot_default-llama-cpp-models.tmpl).

2. Add or edit the corresponding preset in [`home/dot_config/llama.cpp/models.ini.tmpl`](../../../../home/dot_config/llama.cpp/models.ini.tmpl). Companion GGUFs (mmproj, draft) are extra manifest lines referenced from that preset; they are not router ids.

3. Fan the new router id out to every consumer in the same change:

   - Pi: [`home/dot_pi/agent/readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json) and [`readonly_models.personal.json`](../../../../home/dot_pi/agent/readonly_models.personal.json)
   - Codex: [`home/dot_codex/readonly_llama-cpp-model-catalog.json`](../../../../home/dot_codex/readonly_llama-cpp-model-catalog.json) and `LOCAL_MODELS` in [`home/exact_lib/exact_,codex/main.py`](../../../../home/exact_lib/exact_,codex/main.py)
   - OpenCode: both [`readonly_opencode.work.jsonc`](../../../../home/dot_config/opencode/readonly_opencode.work.jsonc) and [`readonly_opencode.personal.jsonc`](../../../../home/dot_config/opencode/readonly_opencode.personal.jsonc)
   - Fish completions for `,claude-llama-cpp`, `,codex-llama-cpp`, `,cursor-llama-cpp`, and `,opencode-llama-cpp`
   - `python3 scripts/model_mirrors.py generate`
   - llama.cpp docs under `docs/topics/ai-assistants/llama-cpp/`

4. Apply:

```bash
chezmoi apply
```

The sync hook is:

- [`home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl)

It hashes both the manifest and the [`scripts/sync_llama_cpp_models.py`](../../../../scripts/sync_llama_cpp_models.py) helper so `chezmoi apply` re-runs on any change to either.

## Verification

```bash
ls -la ~/.llama.cpp/models/
,llama-cpp serve
,llama-cpp status
```

Preview what the manifest renders to on this host:

```bash
chezmoi execute-template < ~/.local/share/chezmoi/home/readonly_dot_default-llama-cpp-models.tmpl
```

## Rollback / Undo

1. Remove the line from [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../../../home/readonly_dot_default-llama-cpp-models.tmpl).
2. Remove the matching preset from [`home/dot_config/llama.cpp/models.ini.tmpl`](../../../../home/dot_config/llama.cpp/models.ini.tmpl).
3. Remove the router id from the Pi/Codex/OpenCode catalogs, `,codex` `LOCAL_MODELS`, fish completions, and regenerate the model mirror.
4. Re-apply:

```bash
chezmoi apply
```

1. Optionally delete the on-disk weights:

```bash
rm -f ~/.llama.cpp/models/<model>.gguf
```
