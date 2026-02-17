# Pin A Tool Version (ASDF)

Back: [`docs/recipes/index.md`](index.md)

Tools managed by ASDF are pinned in `~/.tool-versions`, which is rendered from a
template in this repo.

## Preconditions

- ASDF is installed and on `PATH`.
- The plugin exists in `home/asdf_plugins.tmpl` (add it first if missing).

## Files

- Plugins: `home/asdf_plugins.tmpl`
- Versions: `home/readonly_dot_tool-versions.tmpl` (installs as `~/.tool-versions`)
- Hook: `home/.chezmoiscripts/run_onchange_after_05-install-asdf-plugins.sh.tmpl`

## Steps

1. Update the pinned version in:
   - `home/readonly_dot_tool-versions.tmpl`

2. Apply:

   ```bash
   chezmoi apply
   ```

The hook will install missing versions and can uninstall versions that are no
longer listed.

## Verification

```bash
asdf current
asdf list
```

## Notes

If you add a brand new tool, you usually need to add both:

- a plugin entry in `home/asdf_plugins.tmpl`
- a version pin in `home/readonly_dot_tool-versions.tmpl`

## Rollback / Undo

1. Revert the version line in `home/readonly_dot_tool-versions.tmpl`.
2. Re-apply:

```bash
chezmoi apply
```

3. Confirm active versions:

```bash
asdf current
```
