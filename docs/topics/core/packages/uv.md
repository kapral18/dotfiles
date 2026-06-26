---
sidebar_position: 16
---

# Add A uv Global Tool

This setup uses `uv` for:

- managing Python versions from `~/.python-version`
- managing globally-installed tools via `uv tool install`

## Preconditions

- `uv` is installed.
- You verified the tool package name.

## Steps

1. Edit the template:
   - [`home/readonly_dot_default-uv-tools.tmpl`](../../../../home/readonly_dot_default-uv-tools.tmpl)

   It installs as `~/.default-uv-tools`.

   Lines may be normal package names, package specs with extras, or git URLs such as `git+https://github.com/antoniorodr/lexy`. The reconcile hook uses the normalized uv tool package key for cleanup/pruning, then reapplies any declared spec with extras, a git URL, or a version/source constraint via `uv tool install --force` so an existing bare tool is not mistaken for the requested spec.

2. Apply:

   ```bash
   chezmoi apply
   ```

Hook:

- [`home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl)

## Verification

```bash
uv tool list
```

## Rollback / Undo

1. Remove the tool from [`home/readonly_dot_default-uv-tools.tmpl`](../../../../home/readonly_dot_default-uv-tools.tmpl).
2. Re-apply:

```bash
chezmoi apply
```
