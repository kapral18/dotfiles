# Refreshing Externals

Back: [`docs/recipes/index.md`](index.md)

This setup uses `chezmoi` externals for a few third-party assets (TPM, bat themes,
Hammerspoon spoons, lowfi tracklists).

Externals are defined in:

- `home/.chezmoiexternal.toml`

## Preconditions

- You changed external definitions or want to force a re-sync.

## Steps

To force-refresh externals when applying:

```bash
chezmoi apply -R always
```

If you want to see what would happen without changing anything:

```bash
chezmoi apply -R always --dry-run --verbose
```

## Verification

- Confirm the expected external directories/files were refreshed.
- Re-run:

```bash
chezmoi apply -R always --dry-run --verbose
```

and confirm no unexpected churn remains.

## Rollback / Undo

- Revert the external declaration changes in `home/.chezmoiexternal.toml`.
- Apply normally:

```bash
chezmoi apply
```
