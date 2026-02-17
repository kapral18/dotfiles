# Apply Custom App Icons

Back: [`docs/recipes/index.md`](index.md)

This setup supports applying custom macOS app icons based on a YAML mapping.

## Preconditions

- You have icon files under `home/app_icons/assets/`.
- Mapping exists in `home/app_icons/icon_mapping.yaml`.
- Dependencies are installed: `fileicon`, `yq`.

## Files

- Mapping: `home/app_icons/icon_mapping.yaml`
- Icon assets: `home/app_icons/assets/`
- Script: `home/exact_bin/executable_,apply-app-icons.tmpl` (installs as `,apply-app-icons`)

## Steps

```bash
,apply-app-icons
```

This will remove any existing custom icon and then set the new one.

## Verification

- Confirm the app icon changed in Finder/Dock.
- Spot-check one mapped app exists:

```bash
ls -d "/Applications/<AppName>.app"
```

- Re-run command and confirm no hard failure:

```bash
,apply-app-icons
```

## Rollback / Undo

- Remove custom icon for one app:

```bash
fileicon remove "/Applications/<AppName>.app"
```

- Or remove/update the mapping entry, then rerun:

```bash
,apply-app-icons
```

## Notes

`home/app_icons/` is kept in the repo but ignored by `chezmoi` (`home/.chezmoiignore`).
The script reads the mapping and assets from the repo source directory.
