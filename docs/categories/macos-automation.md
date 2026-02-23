# macOS Automation

Back: [`docs/categories/index.md`](index.md)

This setup includes macOS-specific automation and preferences.

## Defaults / Settings

The raw scripts live here:

- `home/.osx.core`
- `home/.osx.extra`

They are applied via hooks:

- `home/.chezmoiscripts/run_onchange_after_05-osx.core.sh.tmpl`
- `home/.chezmoiscripts/run_onchange_after_05-osx.extra.sh.tmpl`

These scripts can change system behavior. Expect that some changes require a
logout/restart to fully take effect.

If you want to disable this category entirely, the most direct approach is to
remove or comment out the relevant hook scripts in `home/.chezmoiscripts/`.

## Core Apply Workflow

1. Review local dotfiles changes:

```bash
chezmoi diff
```

2. Apply:

```bash
chezmoi apply
```

3. Reboot/log out if settings did not visually update yet.

You can also run `.osx` scripts directly while debugging:

```bash
bash home/.osx.core
bash home/.osx.extra
```

## Hammerspoon

- Config: `home/dot_hammerspoon/init.lua`

Key pieces:

- Window management hotkeys: `home/dot_hammerspoon/window.lua`
- Grid-mouse (keyboard mouse): `home/dot_hammerspoon/gridmouse.lua` (currently not enabled in `init.lua`)

In `init.lua`, `Hyper` is configured as `ctrl+alt+cmd`.

This setup pulls the `EmmyLua.spoon` via externals:

- `home/.chezmoiexternal.toml`

Workflow:

- Edit modules under `home/dot_hammerspoon/`.
- Reload Hammerspoon config from the app menu.
- Verify configured keybindings in `init.lua` and module files.

## Karabiner

- `home/dot_config/exact_private_karabiner/karabiner.json`

Workflow:

- Edit `karabiner.json`.
- Import/reload through Karabiner-Elements.
- Validate by testing the modified key mapping directly.

## Alfred

- `home/Alfred.alfredpreferences/`

Note: this directory is currently ignored by `chezmoi` via `home/.chezmoiignore`.
It is kept in the repo as a reference/backup rather than being automatically
installed.

## Custom App Icons

- Mapping: `home/app_icons/icon_mapping.yaml`
- Script: `home/exact_bin/executable_,apply-app-icons.tmpl`
- Hook: `home/.chezmoiscripts/run_onchange_after_05-apply-app-icons.sh.tmpl`

Note: `home/app_icons/` is ignored by `chezmoi` via `home/.chezmoiignore`. The
script reads icon assets from the repo source directory.

## Verification

Check a few high-signal defaults:

```bash
defaults read -g KeyRepeat
defaults read com.apple.screencapture location
defaults read net.freemacsoft.AppCleaner SUAutomaticallyUpdate
```

Check icon command wiring:

```bash
command -v ,apply-app-icons
```

## Troubleshooting

- `defaults` changes did not apply:
  - restart affected apps (`Finder`, `Dock`, `SystemUIServer`) or reboot.
- `,apply-app-icons` fails:
  - verify `fileicon` and `yq` are installed.
  - verify `home/app_icons/icon_mapping.yaml` and asset files exist.
- Hook runs but nothing changed:
  - confirm the script hash-trigger input actually changed.

## Related

- Apply custom app icons: [`docs/recipes/apply-custom-app-icons.md`](../recipes/apply-custom-app-icons.md)
- New machine bootstrap: [`docs/recipes/new-machine-bootstrap.md`](../recipes/new-machine-bootstrap.md)
- Debugging hooks: [`docs/recipes/debugging-chezmoi-hooks.md`](../recipes/debugging-chezmoi-hooks.md)
