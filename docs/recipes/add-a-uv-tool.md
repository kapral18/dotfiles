# Add A uv Global Tool

Back: [`docs/recipes/index.md`](index.md)

This setup uses `uv` for:

- managing Python versions from `~/.python-version`
- managing globally-installed tools via `uv tool install`

## Preconditions

- `uv` is installed.
- You verified the tool package name.

## Steps

1. Edit the template:

   - `home/readonly_dot_default-uv-tools.tmpl`

   It installs as `~/.default-uv-tools`.

2. Apply:

   ```bash
   chezmoi apply
   ```

Hook:

- `home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl`

## Verification

```bash
uv tool list
```

## Rollback / Undo

1. Remove the tool from `home/readonly_dot_default-uv-tools.tmpl`.
2. Re-apply:

```bash
chezmoi apply
```
