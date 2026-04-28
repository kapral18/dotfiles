# Add An oMLX Model

Back: [`docs/recipes/index.md`](index.md)

oMLX models are pulled into `~/.omlx/models/` from a curated manifest. Downloads are opt-in and idempotent.

## Preconditions

- `omlx` and `hf` are installed (Brewfile additions in the AI section).
- You ran `chezmoi init` at least once and chose a value for `downloadOmlxModels`. Re-run `chezmoi init` to change it.
- You identified an MLX-compatible Hugging Face repo (look for the `mlx` library tag on the model card).

## Where The List Lives

- [`home/readonly_dot_default-omlx-models.tmpl`](../../home/readonly_dot_default-omlx-models.tmpl)

## Schema

Pipe-delimited, one model per line:

```text
<hf-repo-id>|<local-dir-name>
```

- `hf-repo-id` — Hugging Face repo id (e.g. `NexVeridian/Qwen3.6-35B-A3B-5bit`).
- `local-dir-name` — subdirectory under `~/.omlx/models/` (kebab-case, descriptive).

Lines starting with `#` and blank lines are ignored. Chezmoi template conditionals work natively if a future model should render only for a specific profile; the orchestrator pipes the manifest through `chezmoi execute-template`.

## Steps

1. Add or edit the entry in [`home/readonly_dot_default-omlx-models.tmpl`](../../home/readonly_dot_default-omlx-models.tmpl).

2. Apply:

```bash
chezmoi apply
```

The sync hook is:

- [`home/.chezmoiscripts/run_onchange_after_07-sync-omlx-models.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-sync-omlx-models.sh.tmpl)

It hashes both the manifest and the [`scripts/sync_omlx_models.py`](../../scripts/sync_omlx_models.py) helper so `chezmoi apply` re-runs on any change to either.

## Verification

```bash
ls -la ~/.omlx/models/
omlx serve --model <local-dir-name>
```

Preview what the manifest renders to on this host:

```bash
chezmoi execute-template < ~/.local/share/chezmoi/home/readonly_dot_default-omlx-models.tmpl
```

## Rollback / Undo

1. Remove the line from [`home/readonly_dot_default-omlx-models.tmpl`](../../home/readonly_dot_default-omlx-models.tmpl).
2. Re-apply:

```bash
chezmoi apply
```

1. Optionally delete the on-disk weights:

```bash
rm -rf ~/.omlx/models/<local-dir-name>
```
