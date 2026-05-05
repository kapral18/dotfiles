# Add A llama.cpp Model

Back: [`docs/recipes/index.md`](index.md)

llama.cpp models are pulled into `~/.llama.cpp/models/` from a curated GGUF manifest. Downloads are opt-in and idempotent.

## Preconditions

- `llama-server` and `hf` are installed (Brewfile additions in the AI section).
- You ran `chezmoi init` at least once and chose a value for `downloadLlamaCppModels`. Clear that key from `~/.config/chezmoi/chezmoi.toml` and re-run `chezmoi init` to change it.
- You identified a GGUF Hugging Face repo and the exact `.gguf` filename to download.

## Where The List Lives

- [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../home/readonly_dot_default-llama-cpp-models.tmpl)

## Schema

Pipe-delimited, one model per line:

```text
<hf-repo-id>|<hf-file>
```

- `hf-repo-id` — Hugging Face repo id containing GGUF weights.
- `hf-file` — GGUF filename to place under `~/.llama.cpp/models/`.

Lines starting with `#` and blank lines are ignored. Chezmoi template conditionals work natively if a future model should render only for a specific profile; the orchestrator pipes the manifest through `chezmoi execute-template`.

## Steps

1. Add or edit the entry in [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../home/readonly_dot_default-llama-cpp-models.tmpl).

2. Add or edit the corresponding preset in [`home/dot_config/llama.cpp/models.ini.tmpl`](../../home/dot_config/llama.cpp/models.ini.tmpl).

3. Apply:

```bash
chezmoi apply
```

The sync hook is:

- [`home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl)

It hashes both the manifest and the [`scripts/sync_llama_cpp_models.py`](../../scripts/sync_llama_cpp_models.py) helper so `chezmoi apply` re-runs on any change to either.

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

1. Remove the line from [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../home/readonly_dot_default-llama-cpp-models.tmpl).
2. Remove the matching preset from [`home/dot_config/llama.cpp/models.ini.tmpl`](../../home/dot_config/llama.cpp/models.ini.tmpl).
3. Re-apply:

```bash
chezmoi apply
```

1. Optionally delete the on-disk weights:

```bash
rm -f ~/.llama.cpp/models/<model>.gguf
```
