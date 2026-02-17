# Add A GitHub CLI Extension

Back: [`docs/recipes/index.md`](index.md)

GitHub CLI extensions are managed as a curated list.

## Preconditions

- `gh` is installed and authenticated (`gh auth status`).
- You know the extension repo (`owner/gh-extension`).

## File

- Hook: `home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl`

The list currently lives inside the hook template.

## Steps

1. Add the extension repo (like `owner/gh-something`) to the list in:

   - `home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl`

2. Apply:

   ```bash
   chezmoi apply
   ```

## Verification

```bash
gh extension list
```

## Rollback / Undo

1. Remove the extension entry from:

- `home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl`

2. Uninstall it:

```bash
gh extension remove <owner/gh-extension>
```

3. Re-apply:

```bash
chezmoi apply
```
