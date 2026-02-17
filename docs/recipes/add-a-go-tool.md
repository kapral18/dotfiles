# Add A Go Tool

Back: [`docs/recipes/index.md`](index.md)

Go-installed tools are managed via a list.

## Preconditions

- Go is installed.
- You verified the module path for the tool.

## Steps

1. Add the module path to:

   - `home/readonly_dot_default-golang-pkgs`

   This installs as `~/.default-golang-pkgs`.

2. Apply:

   ```bash
   chezmoi apply
   ```

Hook:

- `home/.chezmoiscripts/run_onchange_after_05-update-golang-pkgs.sh.tmpl`

## Verification

```bash
which <tool>
<tool> --version
```

## Rollback / Undo

1. Remove the module path from `home/readonly_dot_default-golang-pkgs`.
2. Re-apply:

```bash
chezmoi apply
```
