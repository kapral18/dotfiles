---
sidebar_position: 3
---

# Pin A Tool Version (mise)

Tools are pinned in [`home/dot_config/mise/config.toml.tmpl`](../../../../home/dot_config/mise/config.toml.tmpl), installed as `~/.config/mise/config.toml`.

## Preconditions

- `mise` is installed and on `PATH`.

## Files

- Runtime versions: [`home/dot_config/mise/config.toml.tmpl`](../../../../home/dot_config/mise/config.toml.tmpl)
- Hook: [`home/.chezmoiscripts/run_onchange_after_05-install-mise-runtimes.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-install-mise-runtimes.sh.tmpl)

## Steps

1. Update the pinned version(s) under `[tools]` in `config.toml.tmpl`.
2. Apply:

```bash
chezmoi apply
```

The hook runs `mise install --yes` and `mise reshim`.

## Verification

```bash
mise ls --current
```

## Notes

- `mise` respects project `.tool-versions` files if they exist.
- `.nvmrc` support is enabled for Node via `idiomatic_version_file_enable_tools = ["node"]`.
