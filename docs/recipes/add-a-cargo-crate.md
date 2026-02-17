# Add A Cargo Crate

Back: [`docs/recipes/index.md`](index.md)

Cargo-installed CLI tools are managed via a list.

## Preconditions

- `cargo` is installed.
- You verified the crate name (for example with `cargo search <name> --limit 5`).

## Steps

1. Add the crate name (or a full `cargo install` line) to:

   - `home/readonly_dot_default-cargo-crates`

   This installs as `~/.default-cargo-crates`.

2. Apply:

   ```bash
   chezmoi apply
   ```

The hook will install missing crates and uninstall crates no longer listed:

- `home/.chezmoiscripts/run_onchange_after_05-update-cargo-crates.sh.tmpl`

## Verification

```bash
cargo install --list
```

## Rollback / Undo

1. Remove the crate line from `home/readonly_dot_default-cargo-crates`.
2. Re-apply:

```bash
chezmoi apply
```
